# -*- coding: utf-8 -*-
"""市场、估值与业绩工具的口径测试：只用合成数据，不访问网络。"""

import unittest
from datetime import date

import pandas as pd

from huohuo.research_entities.models import EntityInstance
from huohuo.research_entities.toolbox.contracts import ToolCall, ToolRequest
from huohuo.research_entities.toolbox.handlers import valuation


class FakeContext:
    def __init__(self, frames):
        self.frames = frames
        self.calls = []

    def call_akshare(self, function_name, timeout=None, **kwargs):
        self.calls.append((function_name, kwargs))
        return self.frames[function_name]

    def today(self):
        return date(2026, 10, 27)


def call(tool_id, params=None, entities=None, frames=None):
    return ToolCall(
        request=ToolRequest(tool_id=tool_id, params=params or {}),
        entities=entities or [],
        ctx=FakeContext(frames or {}),
    )


def stock():
    return EntityInstance(
        entity_id="SEC:CN:A:600519",
        entity_type_code="ENTITY_01_01",
        canonical_name="贵州茅台",
        identifiers={"security_code": "600519"},
        status="verified",
    )


class StockValuationTests(unittest.TestCase):
    def test_percentile_uses_full_period_not_truncated_records(self):
        frame = pd.DataFrame(
            {"date": [f"2026-01-{day:02d}" for day in range(1, 11)],
             "value": [10, 11, 12, 13, 14, 15, 16, 17, 18, 20]}
        )
        result = valuation.stock_valuation_lookup(
            call("stock_valuation_lookup", {"valuation_indicator": "市盈率(TTM)",
                                            "valuation_period": "近一年", "limit": 2},
                 [stock()], {"stock_zh_valuation_baidu": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["count"], 2)
        self.assertEqual(result.data["latest"]["value"], 20.0)
        # 10 个样本中小于等于 20 的有 10 个，分位必须是 100 而不是截断后的 2 个样本。
        self.assertEqual(result.data["percentile"]["window_points"], 10)
        self.assertEqual(result.data["percentile"]["percentile"], 100.0)
        self.assertEqual(result.data["summary"]["points"], 10)

    def test_rejects_unknown_indicator(self):
        result = valuation.stock_valuation_lookup(
            call("stock_valuation_lookup", {"valuation_indicator": "席勒市盈率"}, [stock()])
        )
        self.assertEqual(result.status, "empty")
        self.assertIn("市盈率(TTM)", result.data["reason"])


class MarketValuationTests(unittest.TestCase):
    def test_index_percentile_uses_full_history(self):
        frame = pd.DataFrame(
            {"日期": ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"],
             "滚动市盈率": [10.0, 12.0, 8.0, 11.0]}
        )
        result = valuation.market_valuation_lookup(
            call("market_valuation_lookup", {"index_name": "沪深300", "limit": 2},
                 frames={"stock_index_pe_lg": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["count"], 2)
        self.assertEqual(result.data["percentile"]["window_points"], 4)
        self.assertEqual(result.data["percentile"]["percentile"], 75.0)

    def test_all_a_reports_source_quantiles(self):
        frame = pd.DataFrame(
            {"date": ["2026-09-30", "2026-10-26"],
             "middlePETTM": [37.19, 34.82],
             "averagePETTM": [58.7, 56.2],
             "middlePELYR": [39.13, 37.28],
             "averagePELYR": [63.17, 59.85],
             "close": [4357.62, 4103.54],
             "quantileInAllHistoryMiddlePeTtm": [None, 0.43644],
             "quantileInRecent10YearsMiddlePeTtm": [None, 0.57007]}
        )
        result = valuation.market_valuation_lookup(
            call("market_valuation_lookup", {"index_name": "全A"},
                 frames={"stock_a_ttm_lyr": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["latest"]["中位PE_TTM"], 34.82)
        self.assertEqual(result.data["latest"]["全历史中位PE_TTM分位"], 0.43644)


class PerformanceForecastTests(unittest.TestCase):
    def test_sorts_by_change_and_keeps_missing_last(self):
        frame = pd.DataFrame(
            {"股票代码": ["000001", "000002", "000003"],
             "股票简称": ["甲公司", "乙公司", "丙公司"],
             "预告类型": ["预增", "预增", "预增"],
             "业绩变动幅度": [50.0, None, 120.0]}
        )
        result = valuation.performance_forecast_lookup(
            call("performance_forecast_lookup", {"report_period": "20260930",
                                                 "forecast_type": "预增", "limit": 10},
                 frames={"stock_yjyg_em": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual([item["股票代码"] for item in result.data["records"]],
                         ["000003", "000001", "000002"])
        self.assertEqual(result.data["matched"], 3)

    def test_unknown_type_is_empty_not_guessed(self):
        result = valuation.performance_forecast_lookup(
            call("performance_forecast_lookup", {"forecast_type": "大幅预增"})
        )
        self.assertEqual(result.status, "empty")
        self.assertIn("预增", result.data["reason"])


if __name__ == "__main__":
    unittest.main()
