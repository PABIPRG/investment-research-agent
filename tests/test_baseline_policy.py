"""绝对条件和定时交付不依赖首次比较基准；语义变化仍需明确基准。"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from huohuo.execution import Repository
from huohuo.mandates import Mandates
from huohuo.market.contracts import UNITS
from huohuo.research_partner.market_sources import collect_market
from huohuo.research_partner.models import EventEnvelope


NUMERIC = {'type': 'numeric', 'metric': 'price', 'operator': '>', 'threshold': 100}
SEMANTIC = {'type': 'semantic', 'claim': 'notable_change'}
QUOTE = {'entity_id': 'SEC:CN:A:600519', 'exchange': 'SSE', 'operation': 'market_quote'}


class BaselineRequirementTests(unittest.TestCase):
    def test_absolute_and_scheduled_rules_need_no_comparison(self):
        from huohuo.research_partner.baseline_policy import requires_comparison_baseline
        for policy in ({'mode': 'scheduled_delivery'}, {'mode': 'due_reminder'},
                       {'mode': 'condition', 'condition': NUMERIC},
                       {'mode': 'periodic_check', 'condition': NUMERIC},
                       {'condition': {'type': 'all', 'conditions': [NUMERIC, NUMERIC]}},
                       {'condition': {'type': 'any', 'conditions': [NUMERIC, NUMERIC]}}):
            with self.subTest(policy=policy):
                self.assertFalse(requires_comparison_baseline(policy))

    def test_semantic_and_mixed_rules_keep_comparison_gate(self):
        from huohuo.research_partner.baseline_policy import requires_comparison_baseline
        for condition in (SEMANTIC, {'type': 'all', 'conditions': [NUMERIC, SEMANTIC]},
                          {'type': 'any', 'conditions': [NUMERIC, {'type': 'all', 'conditions': [SEMANTIC]}]}):
            with self.subTest(condition=condition):
                self.assertTrue(requires_comparison_baseline({'condition': condition}))
                self.assertTrue(requires_comparison_baseline({'mode': 'periodic_check', 'condition': condition}))

    def test_unknown_or_invalid_policy_does_not_bypass_gate(self):
        from huohuo.research_partner.baseline_policy import requires_comparison_baseline
        for policy in (None, {}, {'mode': 'unsupported'}, {'condition': {'type': 'any', 'conditions': []}},
                       {'condition': {'type': 'future_rule'}}, {'condition': {'type': 'all', 'conditions': [None]}}):
            with self.subTest(policy=policy):
                self.assertTrue(requires_comparison_baseline(policy))


class BaselineRecoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name) / 'business.db')
        self.core = Mandates(self.repo, 'baseline-fixture')
        self.core.entities.directory = lambda: {'status': 'ok', 'rows': [{'code': '600519', 'name': '贵州茅台'}],
                                               'source': {'provider': 'fixture'}}
        resolved = self.core.entities.resolve('alice', 'baseline-test', '600519股票')
        confirmation = self.core.entities.confirm('alice', 'baseline-test', resolved['snapshot_id'], resolved['version'],
                                                  {resolved['mentions'][0]['mention_id']: QUOTE['entity_id']}, 'fixture')
        self.cid = confirmation['confirmations'][0]['confirmation_id']

    def tearDown(self):
        self.core.store.close()
        self.tmp.cleanup()

    def create_with_failed_baseline(self, scope, rule):
        view = self.core.create('alice', {'request_key': 'create-rule', 'scope': scope, 'goal': '合成：验证规则门禁',
                                        'contact_note': '仅应用内', 'session_id': 'baseline-test',
                                        'confirmation_id': self.cid, 'contact_rule': rule})
        self.core.tick()
        baseline = self.repo.claim('baseline-fixture')
        # 新的纯日程不再创建无必要的初始研究；需要基准的规则仍验证失败恢复。
        if baseline is not None:
            self.repo.finish(baseline['attempt_id'], baseline['lease_token'],
                             {'status': 'failed', 'error': 'outside_brief_window：首次资料不在约定时段或暂缺'})
        self.core.tick()
        mid = view['mandate']['mandate_id']
        self.assertFalse(self.core.get('alice', mid)['baseline'])
        return mid

    def due(self, mid, mode):
        schedule = self.core.store.list_schedules(mid)[0]
        now = datetime.now(timezone.utc)
        with self.core.store.transaction():
            self.core.store.record_event(EventEnvelope(event_id='synthetic-due', hook_type='schedule.due',
                producer='test-scheduler', occurred_at=now, observed_at=now, subject_ids=[QUOTE['entity_id']],
                payload={'schedule_id': schedule.schedule_id, 'instance_key': 'synthetic-now',
                         'scheduled_at': now.isoformat(), 'mode': mode, 'mandate_id': mid, 'revision': 1}))

    def fresh_quote(self):
        class Source:
            def query(self, request):
                stamp = datetime.now(timezone.utc).isoformat()
                return {'status': 'ok', 'complete': True, 'stale': False, 'as_of': stamp, 'warnings': [],
                        'data': {'items': [{'code': '600519', 'price': 110, 'as_of': stamp,
                                           'time_known': True, 'units': dict(UNITS)}]}}
        self.core.sources.accept('alice', collect_market(QUOTE, Source()))

    def test_brief_due_can_run_after_outside_window_baseline_failure(self):
        mid = self.create_with_failed_baseline(dict(QUOTE, operation='market_brief', period='post'),
                    {'mode': 'scheduled_delivery', 'time': '23:59', 'trading_days_only': False})
        self.due(mid, 'scheduled_delivery')
        self.core.tick()
        job = self.repo.claim('baseline-fixture')
        self.assertIsNotNone(job, '按时交付不能被首次简报基准失败永久阻挡')
        self.assertEqual(job['scope']['operation'], 'market_brief')

    def test_absolute_numeric_source_can_run_after_baseline_failure(self):
        self.create_with_failed_baseline(QUOTE, {'mode': 'condition', 'condition': NUMERIC})
        self.fresh_quote()
        self.core.tick()
        self.assertIsNotNone(self.repo.claim('baseline-fixture'), '绝对价格条件不依赖历史比较基准')

    def test_periodic_numeric_can_run_after_baseline_failure(self):
        mid = self.create_with_failed_baseline(QUOTE, {'mode': 'periodic_check', 'time': '23:59', 'condition': NUMERIC})
        self.due(mid, 'periodic_check')
        self.core.tick()
        self.assertIsNotNone(self.repo.claim('baseline-fixture'))

    def test_semantic_failure_still_waits_without_silent_retry(self):
        self.create_with_failed_baseline(QUOTE, {'mode': 'condition', 'condition': SEMANTIC})
        self.fresh_quote()
        self.core.tick()
        self.assertIsNone(self.repo.claim('baseline-fixture'))
        jobs = self.core.store._connect().execute('SELECT action,status FROM research_jobs').fetchall()
        self.assertEqual(sorted(tuple(row) for row in jobs), [('baseline_review', 'failed'), ('event_review', 'pending')])


if __name__ == '__main__':
    unittest.main()
