"""当前来源已变化时，积压任务与旧结果不能再触发当前提醒。"""
import unittest
from unittest.mock import patch
import test_market_integration as fixtures
from test_market_integration import SCOPE
from huohuo.research_partner.market_sources import collect_market


class MarketSupersessionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.MarketIntegrationTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.core, self.repo = self.f.core, self.f.repo
        self.mid = self.f.create()['mandate']['mandate_id']
        self.core.tick(); self.f.finish(0)

    def source(self, price):
        self.f.market.price = price
        return self.core.sources.accept('alice', collect_market(SCOPE, self.f.market))

    def test_resume_routes_latest_head_not_pending_old_snapshot(self):
        paused = self.core.command('alice', self.mid, 'pause', {
            'request_key': 'pause-case', 'expected_revision': 1, 'expected_generation': 0})
        old = self.source(120); latest = self.source(80)
        self.core.command('alice', self.mid, 'resume', {
            'request_key': 'resume-case', 'expected_revision': 1, 'expected_generation': paused['generation']})
        self.core.tick()
        rows = self.core.store._connect().execute("SELECT trigger_event_id FROM research_jobs WHERE action='event_review'").fetchall()
        self.assertEqual([r[0] for r in rows], [latest])
        self.f.finish(0)
        self.assertEqual(self.core.get('alice', self.mid)['notifications'], [])

    def test_inflight_old_result_is_history_after_new_head(self):
        self.source(120); self.core.tick()
        job = self.repo.claim('fixture')
        doc = self.core.bound_source(job['execution_id'])
        self.source(80)
        evidence = self.repo.save_evidence(job['attempt_id'], job['lease_token'], doc)
        self.repo.finish(job['attempt_id'], job['lease_token'], {
            'status': 'succeeded', 'execution_id': job['execution_id'], 'scope': SCOPE,
            'summary': '合成旧报价', 'evidence_ids': [evidence['evidence_id']]})
        self.core.tick()
        row = self.core.store._connect().execute('SELECT stale FROM research_job_results WHERE run_id=?', (job['attempt_id'],)).fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(self.core.get('alice', self.mid)['notifications'], [])

    def test_queued_delivery_rechecks_head_before_issuing_permit(self):
        self.source(120); self.core.tick()
        with patch.object(self.core.notifications, 'tick'):
            self.f.finish(0)
        queue = self.core.notifications.list('alice')['items']
        self.assertEqual(len(queue), 1)
        self.source(80)
        self.assertIsNone(self.core.notifications.reserve(queue[0]['decision_id']))
        self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'], 'cancelled')
