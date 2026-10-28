"""静默与重试后的行情发送资格必须重新检查，已在途许可不逆向改写。"""
import json
import unittest
from unittest.mock import patch

from huohuo.execution import Repository
from huohuo.mandates import Mandates
import test_market_integration as fixtures


class MarketDeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.MarketIntegrationTests()
        self.fixture.setUp()
        self.core, self.repo = self.fixture.core, self.fixture.repo
        self.fixture.market.price = 110
        self.fixture.create()
        self.core.tick()
        # 在发送前暂停 tick，保留真实业务链产生的 queued 决定。
        with patch.object(self.core.notifications, 'tick'):
            self.fixture.finish(110)
        self.queued = self.core.notifications.list('alice')['items'][0]
        self.did = self.queued['decision_id']

    def tearDown(self):
        self.fixture.tearDown()

    def gate(self):
        from huohuo.notifications.market_gate import current_for_delivery
        return current_for_delivery(self.core, self.did)

    def advance(self):
        clock = self.repo.clock
        self.repo.clock = lambda: clock() + 240

    def test_queued_quote_expires_before_sending(self):
        self.advance()
        self.assertIsNone(self.core.notifications.reserve(self.did), '发送起点不得继续使用四分钟前的行情')
        self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'], 'cancelled')

    def test_fresh_bound_result_passes_without_network(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('must not fetch during send transaction')):
            self.assertTrue(self.gate())
        self.assertIsNotNone(self.core.notifications.reserve(self.did))

    def test_stale_result_or_missing_evidence_is_unknown(self):
        db = self.core.store._connect()
        for change in ('stale', 'missing', 'malformed'):
            with self.subTest(change=change):
                with self.core.store.transaction():
                    row = db.execute('SELECT * FROM research_job_results').fetchone()
                    original = row['structured_result_json']
                    if change == 'stale':
                        db.execute('UPDATE research_job_results SET stale=1')
                    else:
                        body = json.loads(original)
                        body['evidence_ids'] = ['does-not-belong-to-attempt'] if change == 'missing' else None
                        db.execute('UPDATE research_job_results SET structured_result_json=?', (json.dumps(body),))
                    self.assertFalse(self.gate())
                    db.execute('UPDATE research_job_results SET stale=0,structured_result_json=?', (original,))

    def test_unknown_decision_or_missing_attempt_never_grants_market_send(self):
        from huohuo.notifications.market_gate import current_for_delivery
        self.assertFalse(current_for_delivery(self.core, 'unknown'))
        with self.core.store.transaction():
            self.core.store._connect().execute("UPDATE research_job_results SET run_id='missing-attempt'")
            self.assertFalse(self.gate())

    def test_due_reminder_has_no_market_evidence_requirement(self):
        # 直接提醒本身不做行情研究；即使委托 scope 是行情，也不能被资料门禁阻挡。
        with self.core.store.transaction():
            db = self.core.store._connect()
            db.execute("UPDATE research_jobs SET action='due_reminder'")
            db.execute("UPDATE research_job_results SET structured_result_json='{}',run_id='reminder:fixture'")
        self.advance()
        self.assertTrue(self.gate())

    def test_non_market_contract_keeps_existing_delivery_policy(self):
        with self.core.store.transaction():
            db = self.core.store._connect()
            row = db.execute('SELECT scope_json FROM mandate_revisions').fetchone()
            scope = dict(json.loads(row[0]), operation='quote_snapshot')
            db.execute('UPDATE mandate_revisions SET scope_json=?', (json.dumps(scope),))
        self.advance()
        self.assertTrue(self.gate())

    def test_restart_rechecks_persisted_age(self):
        self.core.store.close()
        self.fixture.repo = self.repo = Repository(self.fixture.path)
        self.fixture.core = self.core = Mandates(self.repo, 'fixture')
        self.assertTrue(self.gate())
        self.advance()
        self.assertFalse(self.gate())

    def test_inflight_permit_is_not_rewritten_or_resent(self):
        permit = self.core.notifications.reserve(self.did)
        self.assertIsNotNone(permit)
        self.advance()
        self.assertFalse(self.gate())
        self.assertIsNone(self.core.notifications.reserve(self.did))
        row = self.core.notifications.list('alice')['items'][0]
        self.assertEqual(row['status'], 'in_flight')
        self.assertEqual(row['permit_id'], permit['permit_id'])


if __name__ == '__main__':
    unittest.main()
