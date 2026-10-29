"""价格规则沿用正式执行/证据/联系链，无模型或真实外发。"""
import copy
import json
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from huohuo.contracts import Invalid
from huohuo.execution import Conflict
from huohuo.research_partner.market_sources import collect_market, validate_market_document, bound_metrics
from huohuo.research_partner.market_freshness import fresh_for_contact
import test_market_integration as fixtures
from test_market_integration import SCOPE


class PriceExecutionTests(unittest.TestCase):
    setUp = fixtures.MarketIntegrationTests.setUp
    tearDown = fixtures.MarketIntegrationTests.tearDown
    def create(self):
        self.core.notifications.save('alice', {'expected_revision': 0, 'enabled': True, 'channels': ['app'], 'timezone': 'Asia/Shanghai', 'quiet_hours': None})
        return self.core.create('alice', {'request_key': 'create-first-price', 'scope': SCOPE, 'goal': '合成首次到价提醒', 'contact_note': '仅应用内', 'session_id': 'test', 'confirmation_id': self.cid,
            'contact_rule': {'mode': 'condition', 'condition': {'type': 'numeric', 'metric': 'price', 'operator': '>', 'threshold': 100}, 'notify_on': 'first_entry', 'cooldown_minutes': 0}})

    def server(self):
        return SimpleNamespace(repo=self.repo, mandates=self.core, market=self.market,
                               calendar=self.core.service.calendar, config={'principal': 'alice'})

    def execute(self):
        from huohuo.research_partner.price_execution import run
        self.core.tick()
        job = self.repo.claim('program-price-test')
        self.assertIsNotNone(job)
        result = run(self.server(), job['attempt_id'], job['lease_token'])
        self.assertEqual(result, run(self.server(), job['attempt_id'], job['lease_token']))
        self.core.tick()
        return job

    def test_program_price_unmet_then_met_once_persists_and_uses_bound_source(self):
        from huohuo.research_partner.price_execution import eligible
        mid = self.create()['mandate']['mandate_id']
        self.assertTrue(eligible(self.core.get('alice', mid)['revision']))
        job = self.execute()
        receipt = json.loads(self.core.store._connect().execute('SELECT runtime_receipt FROM attempts WHERE id=?', (job['attempt_id'],)).fetchone()[0])
        self.assertEqual(receipt['session_id'], 'program:price-condition-v1')
        self.assertEqual(self.core.get('alice', mid)['decisions'][-1]['condition_result'], 'unmet')
        self.market.price = 110
        self.core.sources.accept('alice', collect_market(SCOPE, self.market))
        # 执行必须使用触发事件绑定的110，不用已变化的其他报价。
        self.market.price = 90
        self.execute()
        self.assertEqual(len(self.core.get('alice', mid)['notifications']), 1)
        self.market.price = 111
        self.core.sources.accept('alice', collect_market(SCOPE, self.market))
        self.execute()
        view = self.core.get('alice', mid)
        self.assertEqual(len(view['notifications']), 1)
        self.assertEqual(view['notifications'][0]['status'], 'delivered')
        self.assertFalse(view['requires_comparison_baseline'])
        self.assertEqual(view['execution_mode'], 'program_price')
        from huohuo.execution import Repository
        from huohuo.mandates import Mandates
        self.core.store.close()
        self.repo = Repository(self.path); self.core = Mandates(self.repo, 'fixture')
        self.assertEqual(len(self.core.get('alice', mid)['notifications']), 1)

    def test_non_price_or_unbound_execution_rejected(self):
        from huohuo.research_partner.price_execution import eligible, run
        self.assertFalse(eligible({'scope': SCOPE, 'contact_policy': {'condition': {'type': 'semantic', 'claim': 'notable_change'}}}))
        ex = self.repo.create('alice', 'unbound', SCOPE, '仅研究，不是已确认价格规则')
        job = self.repo.claim('test')
        with self.assertRaises(Invalid): run(self.server(), job['attempt_id'], job['lease_token'])

    def test_price_entry_cannot_bypass_missing_trusted_hook(self):
        from huohuo.research_partner.price_execution import run
        self.create(); self.core.tick(); job = self.repo.claim('test')
        self.core.store._connect().execute('UPDATE research_jobs SET trigger_event_id=NULL')
        with self.assertRaises(Invalid): run(self.server(), job['attempt_id'], job['lease_token'])
        self.assertEqual(self.repo.evidence('alice', job['execution_id']), [])

    def test_pause_and_expired_lease_reject_before_write(self):
        from huohuo.research_partner.price_execution import run
        m = self.create(); self.core.tick(); job = self.repo.claim('test')
        self.core.command('alice', m['mandate']['mandate_id'], 'pause',
                          {'request_key': 'pause-price-test', 'expected_revision': 1, 'expected_generation': 0})
        with self.assertRaises(Conflict): run(self.server(), job['attempt_id'], job['lease_token'])
        self.assertEqual(self.repo.evidence('alice', job['execution_id']), [])

    def test_lease_owner_and_unavailable_quote_never_grant_send(self):
        from huohuo.research_partner.price_execution import run
        self.create(); self.core.tick(); job = self.repo.claim('test')
        with self.assertRaises(Conflict): run(self.server(), job['attempt_id'], 'forged')
        wrong = self.server(); wrong.config = {'principal': 'other'}
        with self.assertRaises(PermissionError): run(wrong, job['attempt_id'], job['lease_token'])
        clock = self.repo.clock; self.repo.clock = lambda: clock()+60
        with self.assertRaises(Conflict): run(self.server(), job['attempt_id'], job['lease_token'])
        self.repo.clock = clock
        bad = {'scope': SCOPE, 'status': 'unavailable', 'reason': 'market_source_stale_or_partial'}
        result = run(self.server(), job['attempt_id'], job['lease_token'], loader=lambda _: bad)
        self.assertEqual(result['status'], 'failed')
        self.core.tick()
        self.assertEqual(self.core.notifications.list('alice')['items'], [])

    def test_revise_revokes_already_claimed_price_attempt(self):
        from huohuo.research_partner.price_execution import run
        m = self.create(); self.core.tick(); job = self.repo.claim('test')
        self.core.command('alice', m['mandate']['mandate_id'], 'revise', {
            'request_key': 'revise-price-test', 'expected_revision': 1, 'expected_generation': 0,
            'goal': m['revision']['goal'], 'scope': SCOPE, 'contact_note': '合成改约',
            'contact_rule': {'mode': 'condition', 'condition': {'type': 'numeric', 'metric': 'price', 'operator': '>', 'threshold': 200}}})
        with self.assertRaises(Conflict): run(self.server(), job['attempt_id'], job['lease_token'])
        self.assertEqual(self.repo.evidence('alice', job['execution_id']), [])

    def test_optional_fields_missing_allow_price_but_not_missing_metric(self):
        response = self.market.query({}); response['complete'] = False
        row = response['data']['items'][0]; row['volume_ratio'] = None; row['turnover'] = None
        response['warnings'] = ['合成：量比和换手率未知']
        source = SimpleNamespace(query=lambda _: response)
        doc = collect_market(SCOPE, source)
        self.assertEqual(doc['status'], 'ok')
        validate_market_document(doc, SCOPE)
        self.assertTrue(fresh_for_contact(doc, SCOPE, datetime.now(timezone.utc).timestamp()))
        self.create(); self.core.tick(); job = self.repo.claim('test')
        ev = self.repo.save_evidence(job['attempt_id'], job['lease_token'], doc)
        values = bound_metrics(self.core.store._connect(), job['attempt_id'], {'evidence_ids': [ev['evidence_id']]}, SCOPE)
        self.assertEqual(values['price']['value'], 90)
        self.assertNotIn('volume_ratio', values)
        self.assertNotIn('turnover', values)
        self.assertFalse(fresh_for_contact(doc, SCOPE, datetime.now(timezone.utc).timestamp()+240))
        for patch in ({'price': 0}, {'price': True}, {'time_known': False}, {'code': '000001'}, {'units': {'price': 'USD/share'}}):
            bad = copy.deepcopy(response); bad['data']['items'][0].update(patch)
            self.assertNotEqual(collect_market(SCOPE, SimpleNamespace(query=lambda _: bad))['status'], 'ok')

    def test_first_entry_sustain_can_mature_but_quiet_intent_is_not_duplicated(self):
        from datetime import timedelta
        from huohuo.research_partner.contact import ContactDecisionService, _Outcome
        from huohuo.research_partner.contact_policy import parse_contact_policy
        from huohuo.research_partner.conditions import ConditionOutcome
        from huohuo.research_partner.models import ContactDecision
        m = self.create(); mid = m['mandate']['mandate_id']
        mandate = self.core.store.get_mandate_internal(mid)
        policy = parse_contact_policy({**m['revision']['contact_policy'], 'sustain_seconds': 60})
        service = ContactDecisionService(self.core.store)
        at = datetime.now(timezone.utc)
        condition = ConditionOutcome('met', '合成价格满足')
        candidate = _Outcome('send_candidate', 'condition_met', 'met', condition_key=policy.condition_key)
        self.assertEqual(service._apply_state_gate(mandate, policy, condition, candidate, at).reason_code, 'sustain_pending')
        self.assertEqual(service._apply_state_gate(mandate, policy, condition, candidate, at+timedelta(seconds=61)).decision, 'send_candidate')
        self.core.store.save_contact_decision(ContactDecision(decision_id='DEC_'+'a'*32,
            mandate_id=mid, mandate_revision=1, decision='defer', reason_code='quiet_hours',
            condition_result='met', condition_key=policy.condition_key, dedupe_key='quiet-first-price', created_at=at+timedelta(seconds=61)))
        self.assertEqual(service._apply_state_gate(mandate, policy, condition, candidate, at+timedelta(seconds=62)).reason_code, 'not_first_entry')
