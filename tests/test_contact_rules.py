import unittest
from datetime import datetime, timedelta, timezone
from test_followup import FollowupTests
from huohuo.contracts import Invalid
from huohuo.research_partner.contact_rules import compile_rule
from huohuo.research_partner.conditions import evaluate_condition
from huohuo.research_partner.models import ResearchJobResult
from huohuo.research_partner.schedules import ScheduleService


class ContactRulesTests(unittest.TestCase):
    setUp = FollowupTests.setUp
    tearDown = FollowupTests.tearDown
    create = FollowupTests.create

    def test_missing_operand_does_not_turn_and_true(self):
        scope = {'operation': 'market_quote'}
        numeric = lambda metric: {'type': 'numeric', 'metric': metric, 'operator': '>=', 'threshold': 5}
        rule = compile_rule({'mode': 'condition', 'condition': {
            'type': 'all', 'conditions': [numeric('pct_change'), numeric('volume_ratio')]}}, scope, ['app'])
        result = ResearchJobResult(result_id='RES_'+'a'*32, job_id='JOB_'+'a'*32, run_id='test', outcome='completed',
            structured_result={'metrics': {'pct_change': {'value': 6, 'unit': '%'}}},
            received_at=datetime.now(timezone.utc))
        self.assertEqual(evaluate_condition(rule['condition'], result).result, 'unknown')
        self.assertEqual(rule['max_retries'], 0)

    def test_scope_wrong_units_and_nonfinite_thresholds_are_rejected(self):
        for threshold in [float('nan'), float('inf'), True]:
            with self.assertRaises(Invalid):
                compile_rule({'mode': 'condition', 'condition': {'type': 'numeric',
                    'metric': 'price', 'operator': '>=', 'threshold': threshold}},
                    {'operation': 'market_quote'}, ['app'])
        with self.assertRaises(Invalid):
            compile_rule({'mode': 'condition', 'condition': {'type': 'numeric',
                'metric': 'price', 'operator': '>=', 'threshold': 100}},
                {'operation': 'financial_summary'}, ['app'])

    def test_saved_rule_is_versioned_and_natural_language_is_not_executable(self):
        view = self.create()
        mid = view['mandate']['mandate_id']
        rule = {'mode': 'scheduled_delivery', 'time': '15:30', 'trading_days_only': True}
        updated = self.core.command('alice', mid, 'revise', {
            'request_key': 'rule-save', 'expected_revision': 1, 'expected_generation': 0,
            'goal': view['revision']['goal'], 'scope': view['revision']['scope'],
            'contact_note': '合成备注：任何暴涨都马上通知', 'contact_rule': rule})
        self.assertEqual(updated['revision']['basis']['contact_rule'], rule)
        self.assertEqual(updated['revision']['contact_policy']['mode'], 'scheduled_delivery')
        self.assertEqual(updated['mandate']['current_revision'], 2)
        self.assertNotIn('暴涨', str(updated['revision']['contact_policy']))
        due = datetime.now(timezone.utc) - timedelta(minutes=1)
        db = self.core.store._connect()
        db.execute('UPDATE mandate_schedules SET next_due_at=?', (due.isoformat(),))
        service = ScheduleService(self.core.store)
        self.assertEqual(service.scan(), 0)
        self.assertEqual(db.execute('SELECT next_due_at FROM mandate_schedules WHERE revision=2').fetchone()[0], due.isoformat())


if __name__ == '__main__':
    unittest.main()
