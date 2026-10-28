"""后台计划、取消、租约、候选确认的本地合成回归；不访问真实行情/模型。"""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.strategies.service import Strategies
from huohuo.strategies.storage import Documents
from huohuo.strategies.schedule import DEFAULT
from huohuo.strategies.legacy import gene_archive
from huohuo.strategies.legacy.runtime import runtime
from test_strategy_domain import bars


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = datetime(2025, 10, 6, 8, tzinfo=timezone.utc).timestamp()
        self.repo = Repository(Path(self.tmp.name) / 'test.sqlite', clock=lambda: self.now)
        self.core = Mandates(self.repo, 'background-tests'); self.seq = 0; self.calls = []
        def history(code, start, end):
            self.calls.append(code)
            return {'records': [x for x in bars(count=800) if start <= x['date'] <= end], 'source': 'synthetic:background', 'adjustment': 'qfq'}
        self.api = Strategies(self.core.store, history=history, clock=lambda: self.now)
        self.candidate = {'name': '合成动量', 'kind': 'momentum', 'params': {'n': 5}, 'securities': [{'code': '600519', 'name': '贵州茅台'}], 'direction': '利好', 'rationale': '合成测试假设'}
    def tearDown(self):
        self.core.store.close(); self.tmp.cleanup()
    def command(self, action, payload):
        self.seq += 1
        p = self.api.prepare('alice', 'chat', {'action': action, 'payload': payload, 'request_key': f'q{self.seq}'})
        return self.api.commit('alice', 'chat', {'preview_id': p['preview_id'], 'request_key': p['request_key']})
    def plan(self, **changes):
        current = self.api.read('alice')['automation']
        return self.command('schedule', {k: changes.get(k, current[k]) for k in DEFAULT})
    def create(self): return self.command('create', self.candidate)['strategy']
    def ready(self, **changes):
        s = self.create(); self.plan(enabled=True, strategy_ids=[s['id']], **changes)
        self.now += 3601
        return s
    def event(self, **changes):
        return {'id': 'event-1', 'source': 'synthetic:news', 'observed_at': self.now, 'title': '合成事件', 'summary': '仅用于测试事件路径', 'securities': self.candidate['securities'], 'evidence_ref': 'synthetic:evidence-1', **changes}
    def drain(self):
        out = []
        for _ in range(10):
            value = self.api.background_tick('alice'); out.append(value)
            if value.get('status') == 'idle': break
        return out
    def test_disabled_is_no_work_then_confirmed_plan_runs_and_deduplicates(self):
        self.create()
        for _ in range(2): self.assertEqual(self.api.background_tick('alice')['status'], 'idle')
        self.assertEqual(self.calls, [])
        s = self.api.read('alice')['strategies'][0]
        self.plan(enabled=True, strategy_ids=[s['id']]); self.now += 3601
        self.drain(); view = self.api.read('alice')
        self.assertEqual(view['strategies'][0]['status'], 'active')
        self.assertEqual(view['attribution']['days_of_data'], 1)
        self.assertTrue(view['pool']['closed_loop_enabled'])
        self.assertIsNotNone(view['pool']['recent_run_at'])
        count = len(view['runs']); self.drain()
        self.assertEqual(len(self.api.read('alice')['runs']), count)
        self.assertFalse(any(r['action'] == 'apply' for r in view['runs']))
    def test_disable_in_flight_rejects_late_result(self):
        s = self.ready(actions=['backtest']); old = self.api.history
        def blocking(*args):
            self.plan(enabled=False)
            return old(*args)
        self.api.history = blocking
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['status'], 'cancelled')
        self.assertEqual(self.api.read('alice')['strategies'][0]['status'], 'candidate')
        self.assertEqual(self.api.background_tick('alice')['status'], 'idle')
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM result_outbox').fetchone()[0],0)
    def test_pending_restored_and_running_interrupted_not_replayed(self):
        self.ready()
        first = self.api.background_tick('alice')
        self.assertEqual(first['run']['status'], 'completed')
        self.api.recovery(); self.drain()
        self.assertEqual(self.api.read('alice')['attribution']['days_of_data'], 1)
        db = self.core.store._connect()
        self.now += 86400
        self.core.tick()
        job=self.api.tasks.claim('alice','synthetic-crash',lane='strategy_compute')
        self.assertIsNotNone(job)
        self.now += 31; self.api.recovery()
        self.assertEqual(self.repo.get('alice',job['execution_id'])['status'],'interrupted')
    def test_plan_revision_and_invalid_autoapply(self):
        s = self.create()
        with self.assertRaises(Invalid): self.plan(enabled=True, strategy_ids=[s['id']], actions=['apply'])
        p = self.api.prepare('alice', 'chat', {'action': 'schedule', 'payload': DEFAULT, 'request_key': 'stale'})
        self.plan(enabled=False)
        r = self.api.commit('alice', 'chat', {'preview_id': p['preview_id'], 'request_key': 'stale'})
        self.assertEqual(r['run']['status'], 'failed')
    def test_model_candidate_staged_and_confirmation_scoped(self):
        self.ready(event_candidates=True)
        event = self.event(); one = self.api.ingest_events('alice', [event]); two = self.api.ingest_events('alice', [event])
        self.assertEqual(one, two)
        job = self.api.planner_claim('alice', 'worker')
        self.assertIsNotNone(job); self.assertIsNone(self.api.planner_claim('alice', 'other'))
        candidate = {**self.candidate, 'params': {'n': 8}}
        result = {'status': 'completed', 'candidates': [candidate]}
        r = self.api.planner_finish('alice', job['job_id'], job['lease_token'], result)
        self.assertEqual(r, self.api.planner_finish('alice', job['job_id'], job['lease_token'], result))
        self.assertEqual(len(self.api.read('alice')['strategies']), 1)
        sid = r['suggestions'][0]
        self.assertEqual(self.api.read('bob')['suggestions'], [])
        p=self.api.prepare('alice','chat',{'request_key':'candidate-scope','action':'accept_suggestion','payload':{'suggestion_id':sid}})
        self.assertIn('贵州茅台（600519）',p['summary'])
        self.assertIn('8',p['summary'])
        accepted = self.command('accept_suggestion', {'suggestion_id': sid})
        self.assertEqual(accepted['run']['strategy_id'],accepted['strategy']['id'])
        self.assertEqual(accepted['run']['subjects'],[accepted['strategy']['id']])
        self.assertEqual(accepted['strategy']['status'], 'candidate')
        self.assertNotIn(accepted['strategy']['id'], self.api.read('alice')['automation']['strategy_ids'])
        self.assertEqual(len(self.api.read('alice')['strategies']), 2)
    def test_expired_cancelled_and_out_of_scope_planner_rejected(self):
        self.ready(event_candidates=True); self.api.ingest_events('alice', [self.event()])
        job = self.api.planner_claim('alice', 'worker')
        bad = {**self.candidate, 'securities': [{'code': '000001', 'name': '平安银行'}]}
        with self.assertRaises(Invalid): self.api.planner_finish('alice', job['job_id'], job['lease_token'], {'status': 'completed', 'candidates': [bad]})
        with self.assertRaises(Conflict): self.api.planner_finish('alice', job['job_id'], 'forged', {'status': 'completed', 'candidates': []})
        self.plan(enabled=False)
        with self.assertRaises(Conflict): self.api.planner_finish('alice', job['job_id'], job['lease_token'], {'status': 'completed', 'candidates': []})
        self.plan(enabled=True); self.api.ingest_events('alice', [self.event()])
        newer = self.api.planner_claim('alice', 'worker'); self.now += 121
        with self.assertRaises(Conflict): self.api.planner_heartbeat('alice', newer['job_id'], newer['lease_token'])
        self.assertIsNone(self.api.planner_claim('alice', 'worker'))
    def test_event_validation_and_owner_scope(self):
        self.ready(event_candidates=True)
        with self.assertRaises(Invalid): self.api.ingest_events('alice', [self.event(observed_at=self.now-90000)])
        self.assertEqual(self.api.ingest_events('bob', [self.event()])['queued'], [])
        self.assertIsNone(self.api.planner_claim('bob', 'worker'))
        self.api.ingest_events('alice', [self.event()])
        with self.assertRaises(Conflict): self.api.ingest_events('alice', [self.event(summary='changed')])
    def test_archive_recall_is_real_staged_path_not_auto_activation(self):
        s = self.ready(actions=['evolve'], archive_recall=True)
        docs = Documents(self.core.store, 'alice')
        with self.core.store.transaction(), runtime(lambda: self.now):
            value = docs.get('strategies', s['id']); value['status'] = 'retired'
            value['gene']['regime_gate'] = {'allow': ['trend_up','trend_down','oscillation','high_vol']}; docs.set('strategies', s['id'], value)
            gene_archive.archive_record(docs, value, reason='synthetic retirement')
            day = self.api.today().isoformat()
        old=self.api.history
        old.index=lambda start,end: old('000300',start,end)
        self.drain(); view = self.api.read('alice')
        self.assertEqual(len(view['suggestions']), 1)
        self.assertEqual(view['strategies'][0]['status'], 'retired')
        r = self.command('accept_suggestion', {'suggestion_id': view['suggestions'][0]['id']})
        self.assertEqual(r['strategy']['mutated_from'], s['id'])
        self.assertEqual(r['strategy']['status'], 'candidate')
        self.assertEqual(r['strategy']['backtest'], {})
        self.assertNotEqual(r['strategy']['id'], s['id'])

    def test_recall_refresh_precedes_evolution_and_keeps_preview_valid(self):
        s = self.ready(actions=['evolve'], archive_recall=True)
        docs = Documents(self.core.store, 'alice')
        with self.core.store.transaction():
            docs.set('strategies', s['id'], {**s, 'status': 'active', 'verification_status': 'passed', 'backtest': {'thresholds_pass': True}})
            for i, nav in enumerate([1, 1.01, 1.02, 1.03, 1.05]):
                docs.set('shadow_equity', f'2025-09-{20+i:02}', {'overall_nav': nav, 'strategies': {s['id']: {'nav': nav, 'initial_capital': 100000, 'equity': nav*100000}}})
        old = self.api.history; old.index = lambda start, end: old('000300', start, end)
        runs = self.drain()
        self.assertEqual([r['run']['action'] for r in runs if 'run' in r], ['recall', 'evolve'])
        self.assertTrue(self.api.read('alice', s['id'])['preview']['valid'])

    def test_cross_day_pending_work_is_not_relabelled_with_today_results(self):
        self.ready(); self.api.background_tick('alice')
        db = self.core.store._connect()
        pending = [r['id'] for r in self.api.read('alice')['background_jobs'] if r['status']=='pending']
        self.api.recovery(); self.now += 86400
        self.drain()
        for jid in pending:
            row = next(r for r in self.api.read('alice')['background_jobs'] if r['id']==jid)
            self.assertEqual(row['status'], 'cancelled')
            self.assertIn('合并', row['error'])
        current = [r for r in self.api.read('alice')['background_jobs'] if r['status']=='completed' and r['action']=='shadow']
        self.assertTrue(current)
        self.assertTrue(all(r['day'] == self.api.today().isoformat() for r in current))

    def test_news_is_collected_by_strategy_mandate_and_queued_once(self):
        self.ready(event_candidates=True, actions=['evolve'])
        seen = []
        def source(securities):
            seen.append(securities); return [self.event()]
        self.api.event_source = source
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['action'], 'events')
        self.assertEqual(r['event_count'], 1)
        self.assertEqual(seen, [self.candidate['securities']])
        self.assertEqual(len(r['queued']), 1)
        self.assertIsNotNone(self.api.planner_claim('alice', 'worker'))
        self.drain(); self.assertEqual(len(seen), 1)

    def test_stop_during_news_collection_drops_late_events(self):
        self.ready(event_candidates=True)
        def source(_):
            self.plan(enabled=False); return [self.event()]
        self.api.event_source = source
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['status'], 'cancelled')
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM strategy_events').fetchone()[0], 0)
        self.assertIsNone(self.api.planner_claim('alice', 'worker'))

    def test_news_failure_and_missing_provider_are_not_successful_empty(self):
        self.ready(event_candidates=True)
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['status'], 'failed')
        self.assertIn('尚未装配', r['run']['error'])
        self.now += 86400
        self.api.event_source = lambda _: (_ for _ in ()).throw(Invalid('source unavailable'))
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['status'], 'failed')
        self.assertIn('来源读取失败', r['run']['error'])
        self.assertEqual(self.api.read('alice')['planner_jobs'], [])

    def test_unknown_news_run_is_interrupted_not_replayed_on_recovery(self):
        self.ready(event_candidates=True); seen = []
        def source(_):
            seen.append(1); raise SystemExit('synthetic process termination')
        self.api.event_source = source
        with self.assertRaises(SystemExit): self.api.background_tick('alice')
        self.now += 31; self.api.recovery(); self.drain()
        self.assertEqual(seen, [1])
        row = next(r for r in self.api.read('alice')['background_jobs'] if r['action']=='events')
        self.assertEqual(row['status'], 'interrupted')

    def test_news_source_cannot_expand_authorized_security_scope(self):
        self.ready(event_candidates=True)
        self.api.event_source = lambda _: [self.event(securities=[{'code': '000001', 'name': '平安银行'}])]
        r = self.api.background_tick('alice')
        self.assertEqual(r['run']['status'], 'failed')
        self.assertEqual(self.api.read('alice')['planner_jobs'], [])

    def test_schedule_receipt_only_links_selected_scope(self):
        first=self.create()
        self.command('create',{**self.candidate,'params':{'n':9}})
        result=self.plan(enabled=True,strategy_ids=[first['id']])
        self.assertEqual(result['run']['strategy_id'],'strategy_plan')
        self.assertEqual(result['run']['subjects'],[first['id']])

if __name__ == '__main__': unittest.main()
