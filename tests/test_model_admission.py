"""真实委托、事件与租约；合成行情，不调用模型或外发。"""
import json
import unittest
import threading
from types import SimpleNamespace
from huohuo.execution import Conflict
from huohuo.research_partner.market_sources import collect_market
import test_market_integration as fixtures
from test_market_integration import SCOPE


class AdmissionTests(unittest.TestCase):
    setUp = fixtures.MarketIntegrationTests.setUp
    tearDown = fixtures.MarketIntegrationTests.tearDown

    def create(self, condition=None, **changes):
        body = dict(request_key='gate-create', scope=SCOPE, goal='合成：按约跟进', contact_note='仅应用内',
                    session_id='test', confirmation_id=self.cid)
        if condition:
            body['contact_rule'] = dict(mode='condition', condition=condition, cooldown_minutes=0)
        body.update(changes)
        return self.core.create('alice', body)

    def server(self):
        return SimpleNamespace(repo=self.repo, mandates=self.core, market=self.market,
                               calendar=self.core.service.calendar, config={'principal': 'alice'})

    def claim(self):
        self.core.tick()
        job = self.repo.claim('gate-test')
        self.assertIsNotNone(job)
        return job

    def admit(self, job, phase='prepare', server=None):
        from huohuo.research_partner.model_admission import admit
        return admit(server or self.server(), job['attempt_id'], job['lease_token'], phase)

    def test_unbound_execution_without_explicit_request_cannot_call_model(self):
        self.repo.create('alice', 'orphan', SCOPE, '不能靠任务存在取得授权')
        job = self.claim()
        self.assertEqual(self.admit(job)['mode'], 'blocked')
        self.assertEqual(self.admit(job, 'submit')['mode'], 'blocked')

    def test_missing_or_unmatched_hook_blocks_already_queued_task(self):
        self.create()
        job = self.claim()
        db = self.core.store._connect()
        db.execute('UPDATE research_jobs SET trigger_event_id=NULL')
        self.assertEqual(self.admit(job)['mode'], 'blocked')

    def test_numeric_unmet_and_met_execute_without_model_and_keep_evidence(self):
        from huohuo.research_partner.model_admission import run_program
        self.core.notifications.save('alice', {'expected_revision': 0, 'enabled': True, 'channels': ['app'],
                                              'timezone': 'Asia/Shanghai', 'quiet_hours': None})
        m = self.create(dict(type='numeric', metric='price', operator='>', threshold=100))
        first = self.claim()
        self.assertEqual(self.admit(first)['mode'], 'program')
        result = run_program(self.server(), first['attempt_id'], first['lease_token'])
        self.assertEqual(result, run_program(self.server(), first['attempt_id'], first['lease_token']))
        receipt = json.loads(self.core.store._connect().execute('SELECT runtime_receipt FROM attempts WHERE id=?', (first['attempt_id'],)).fetchone()[0])
        self.assertEqual(receipt['session_id'], 'program:price-condition-v1')
        self.core.tick()
        view = self.core.get('alice', m['mandate']['mandate_id'])
        self.assertEqual(view['decisions'][-1]['condition_result'], 'unmet')
        self.assertEqual(view['notifications'], [])
        self.market.price = 110
        doc = collect_market(SCOPE, self.market)
        self.core.sources.accept('alice', doc)
        second = self.claim()
        self.assertEqual(self.admit(second, 'submit')['mode'], 'program')
        run_program(self.server(), second['attempt_id'], second['lease_token'])
        self.core.tick()
        self.assertEqual(len(self.core.get('alice', m['mandate']['mandate_id'])['notifications']), 1)
        self.core.sources.accept('alice', doc)
        self.core.tick()
        self.assertIsNone(self.repo.claim('duplicate'))
        self.assertEqual(self.core.store._connect().execute("SELECT count(*) FROM events WHERE kind='model.submission_reserved'").fetchone()[0], 0)

    def test_semantic_initial_review_is_explicit_and_submit_is_single_use(self):
        self.create()
        job = self.claim()
        self.assertEqual(self.admit(job)['mode'], 'model')
        self.assertEqual(self.admit(job)['mode'], 'model')
        self.assertEqual(self.admit(job, 'submit')['mode'], 'model')
        self.assertEqual(self.admit(job)['mode'], 'blocked')
        self.assertEqual(self.admit(job, 'submit')['mode'], 'blocked')
        records = self.repo.history('alice', job['execution_id'])
        reserved = [r for r in records if r['kind'] == 'model.submission_reserved']
        self.assertEqual(len(reserved), 1)
        self.assertEqual(reserved[0]['data']['attempt_id'], job['attempt_id'])
        self.assertIn('trigger_event_id', reserved[0]['data'])

    def test_pause_between_prepare_and_submit_revokes_capability(self):
        m = self.create()
        job = self.claim()
        self.assertEqual(self.admit(job)['mode'], 'model')
        self.core.command('alice', m['mandate']['mandate_id'], 'pause',
                          dict(request_key='pause-gate', expected_revision=1, expected_generation=0))
        with self.assertRaises(Conflict):
            self.admit(job, 'submit')

    def test_wrong_owner_forged_token_and_expired_lease_rejected(self):
        from huohuo.research_partner.model_admission import admit
        self.create()
        job = self.claim()
        wrong = self.server(); wrong.config = {'principal': 'bob'}
        with self.assertRaises(PermissionError): self.admit(job, server=wrong)
        with self.assertRaises(Conflict): admit(self.server(), job['attempt_id'], 'forged', 'prepare')
        clock = self.repo.clock; self.repo.clock = lambda: clock() + 31
        with self.assertRaises(Conflict): self.admit(job, 'submit')

    def test_scheduled_delivery_and_direct_reminder_do_not_run_on_creation(self):
        for mode in ('scheduled_delivery', 'due_reminder', 'periodic_check'):
            rule = dict(mode=mode, time='23:59', trading_days_only=False)
            if mode == 'periodic_check':
                rule['condition'] = dict(type='numeric', metric='price', operator='>', threshold=100)
            self.create(request_key='schedule-' + mode, contact_rule=rule)
        self.core.tick()
        self.assertIsNone(self.repo.claim('too-early'))

    def test_unknown_numeric_source_never_falls_back_to_model(self):
        from huohuo.research_partner.model_admission import run_program
        self.create(dict(type='numeric', metric='price', operator='>', threshold=100))
        job = self.claim()
        self.assertEqual(self.admit(job)['mode'], 'program')
        result = run_program(self.server(), job['attempt_id'], job['lease_token'], loader=lambda _: {'status': 'unavailable'})
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(self.repo.claim('no-fallback'))

    def test_mixed_contact_rule_does_not_invent_research_trigger(self):
        self.create(dict(type='any', conditions=[dict(type='numeric', metric='price', operator='>', threshold=100),
                                                dict(type='semantic', claim='经营恶化')]))
        self.assertEqual(self.admit(self.claim())['mode'], 'blocked')

    def test_numeric_submit_cannot_be_used_to_start_model(self):
        self.create(dict(type='numeric', metric='price', operator='>', threshold=100))
        job = self.claim()
        self.assertEqual(self.admit(job, 'submit')['mode'], 'program')

    def test_actual_due_hook_allows_delivery_but_numeric_periodic_is_program(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 28, 7, 0, tzinfo=timezone.utc).timestamp()
        self.repo.clock = lambda: now
        for mode in ('scheduled_delivery', 'periodic_check', 'due_reminder'):
            rule = dict(mode=mode, time='15:01', trading_days_only=False)
            if mode == 'periodic_check':
                rule['condition'] = dict(type='numeric', metric='price', operator='>', threshold=100)
            self.create(request_key='due-' + mode, contact_rule=rule)
        self.core.tick()
        self.assertIsNone(self.repo.claim('before-due'))
        now += 61
        self.core.tick()
        decisions = []
        for _ in range(2):
            job = self.repo.claim('at-due')
            self.assertIsNotNone(job)
            decisions.append(self.admit(job)['mode'])
        self.assertEqual(sorted(decisions), ['model', 'program'])
        self.assertIsNone(self.repo.claim('reminder-needs-no-execution'))

    def test_missing_cancel_generation_is_not_a_valid_legacy_bypass(self):
        self.create()
        job = self.claim()
        self.core.store._connect().execute('DELETE FROM mandate_generation')
        self.assertEqual(self.admit(job)['mode'], 'blocked')

    def test_submit_reservation_serializes_and_survives_restart(self):
        from huohuo.execution import Repository
        from huohuo.mandates import Mandates
        self.create()
        job = self.claim()
        barrier = threading.Barrier(2)
        values, errors = [], []
        def submit():
            try:
                barrier.wait(); values.append(self.admit(job, 'submit')['mode'])
            except Exception as exc: errors.append(type(exc).__name__)
            finally: self.core.store.close_current_connection()
        threads = [threading.Thread(target=submit) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(values), ['blocked', 'model'])
        self.core.store.close()
        self.repo = Repository(self.path); self.core = Mandates(self.repo, 'fixture')
        self.assertEqual(self.admit(job, 'submit')['mode'], 'blocked')

    def test_semantic_source_rechecks_dependency_freshness_and_supersession(self):
        self.create()
        baseline = self.claim()
        doc = collect_market(SCOPE, self.market)
        ev = self.repo.save_evidence(baseline['attempt_id'], baseline['lease_token'], doc)
        self.repo.finish(baseline['attempt_id'], baseline['lease_token'], dict(status='succeeded',
            execution_id=baseline['execution_id'], scope=SCOPE, evidence_ids=[ev['evidence_id']], summary='合成初始基准'))
        self.core.tick()
        self.market.price = 110
        self.core.sources.accept('alice', collect_market(SCOPE, self.market))
        job = self.claim()
        self.assertEqual(self.admit(job)['mode'], 'model')
        db = self.core.store._connect()
        db.execute('UPDATE tracking_dependencies SET active=0')
        self.assertEqual(self.admit(job)['mode'], 'blocked')
        db.execute('UPDATE tracking_dependencies SET active=1')
        self.market.price = 111
        self.core.sources.accept('alice', collect_market(SCOPE, self.market))
        self.assertEqual(self.admit(job, 'submit')['reason'], 'source_superseded')

    def test_stale_source_does_not_grant_model_even_with_live_lease(self):
        self.test_semantic_source_rechecks_dependency_freshness_and_supersession()
        job = self.claim()
        clock = self.repo.clock; later = clock() + 241
        self.repo.clock = lambda: later
        self.core.store._connect().execute('UPDATE attempts SET lease_until=? WHERE id=?', (later+30, job['attempt_id']))
        self.assertEqual(self.admit(job)['reason'], 'hook_source_stale_or_unknown')


class AdmissionApiTests(unittest.TestCase):
    from test_api import ApiTests as _Fixture
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown
    call = _Fixture.call

    def test_explicit_user_request_has_trusted_origin_and_worker_only_gate(self):
        from test_api import SCOPE as QUOTE_SCOPE
        _, created = self.call('/executions', dict(request_key='manual-gate', scope=QUOTE_SCOPE, question='用户明确请求'))
        for old in ({'worker_id': 'old-worker'}, {'worker_id': 'old-worker', 'admission_policy': 'old-policy'}):
            self.assertEqual(self.call('/worker/claim', old, 'worker-secret')[0], 400)
        self.assertEqual(self.service.repo.get('owner', created['execution_id'])['status'], 'queued')
        _, job = self.call('/worker/claim', {'worker_id': 'api-gate', 'admission_policy': 'hook-model-gate-v1'}, 'worker-secret')
        path = '/worker/attempts/' + job['attempt_id'] + '/model-admission'
        header = {'X-Attempt-Token': job['lease_token']}
        self.assertEqual(self.call(path, {'phase': 'prepare'}, headers=header)[0], 403)
        self.assertEqual(self.call(path, {'phase': 'prepare'}, 'worker-secret', {'X-Attempt-Token': 'forged'})[0], 409)
        status, decision = self.call(path, {'phase': 'prepare'}, 'worker-secret', header)
        self.assertEqual(status, 200)
        self.assertEqual(decision['mode'], 'model')
        self.assertEqual(decision['execution_id'], created['execution_id'])
        self.assertEqual(self.call(path, {'phase': 'submit'}, 'worker-secret', header)[1]['mode'], 'model')
        self.assertEqual(self.call(path, {'phase': 'submit'}, 'worker-secret', header)[1]['mode'], 'blocked')


class StrategyAdmissionTests(unittest.TestCase):
    from test_strategy_background import BackgroundTests as _Fixture
    setUp = _Fixture.setUp
    tearDown = _Fixture.tearDown
    command = _Fixture.command
    create = _Fixture.create
    plan = _Fixture.plan
    ready = _Fixture.ready
    event = _Fixture.event

    def test_candidate_requires_current_strategy_source_and_compute_is_program(self):
        from huohuo.research_partner.model_admission import admit
        self.ready(event_candidates=True)
        self.api.ingest_events('alice', [self.event()])
        job = self.api.planner_claim('alice', 'gate-strategy')
        server = SimpleNamespace(repo=self.repo, mandates=self.core, strategies=self.api, config={'principal': 'alice'})
        self.assertEqual(admit(server, job['attempt_id'], job['lease_token'], 'prepare')['mode'], 'model')
        db = self.core.store._connect()
        db.execute('UPDATE research_jobs SET trigger_event_id=NULL WHERE job_id=?', (job['job_id'],))
        self.assertEqual(admit(server, job['attempt_id'], job['lease_token'], 'submit')['mode'], 'blocked')
