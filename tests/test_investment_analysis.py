"""旧成本集中度能力在统一事实读模型中的回归，不涉及实时估值。"""
import unittest
from huohuo.investment.analysis import cost_analysis


class InvestmentAnalysisTests(unittest.TestCase):
    def test_complete_cost_weights_and_zero_cost(self):
        result = cost_analysis([
            {'ticker': '600519', 'name': '甲', 'quantity': 10, 'cost_price': 20},
            {'ticker': '000001', 'name': '乙', 'quantity': 20, 'cost_price': 5},
            {'ticker': '513130', 'name': '丙', 'quantity': 100, 'cost_price': 0},
        ], True)
        self.assertEqual(result['total_cost_value'], 300)
        self.assertEqual(result['top_position_cost_weight'], 66.6667)
        self.assertEqual(result['positions'][2]['cost_weight'], 0)
        self.assertFalse(result['is_market_value'])

    def test_unknown_cost_never_normalizes_partial_holdings_to_full_weight(self):
        result = cost_analysis([
            {'ticker': '600519', 'quantity': 10, 'cost_price': 20},
            {'ticker': '000001', 'quantity': 20, 'cost_price': None},
        ], True)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['known_cost_subtotal'], 200)
        self.assertIsNone(result['total_cost_value'])
        self.assertIsNone(result['top_position_cost_weight'])
        self.assertTrue(all(x['cost_weight'] is None for x in result['positions']))

    def test_unrecorded_and_confirmed_empty_differ(self):
        self.assertEqual(cost_analysis([], False)['status'], 'not_recorded')
        self.assertEqual(cost_analysis([], True)['total_cost_value'], 0)
        self.assertEqual(cost_analysis([], True)['status'], 'empty')

    def test_all_zero_cost_has_no_division_or_invented_weight(self):
        result = cost_analysis([{'ticker': '513130', 'quantity': 100, 'cost_price': 0}], True)
        self.assertEqual(result['total_cost_value'], 0)
        self.assertIsNone(result['top_position_cost_weight'])
