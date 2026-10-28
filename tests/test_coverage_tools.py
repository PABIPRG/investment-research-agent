# -*- coding: utf-8 -*-
"""研报、公告、海外行情、分钟线与债券收益率工具的合成数据测试。"""

import unittest
from datetime import date

import pandas as pd

from huohuo.research_entities.models import EntityInstance
from huohuo.research_entities.toolbox.contracts import ToolCall, ToolRequest
from huohuo.research_entities.toolbox.handlers import coverage


def _calendar_frame():
    days = pd.date_range("2026-01-01", "2026-12-31", freq="B")
    return pd.DataFrame({"trade_date": [item.date() for item in days]})


_LAST_CONTEXT = None


class FakeContext:
    def __init__(self, frames):
        global _LAST_CONTEXT
        self.frames = dict(frames)
        self.frames.setdefault("tool_trade_date_hist_sina", _calendar_frame())
        self.calls = []
        _LAST_CONTEXT = self

    def call_akshare(self, function_name, timeout=None, **kwargs):
        self.calls.append((function_name, kwargs))
        value = self.frames[function_name]
        if isinstance(value, Exception):
            raise value
        return value

    def today(self):
        return date(2026, 10, 27)


def call(tool_id, params=None, entities=None, frames=None):
    call_obj = ToolCall(
        request=ToolRequest(tool_id=tool_id, params=params or {}),
        entities=entities or [],
        ctx=FakeContext(frames or {}),
    )
    return call_obj


def calls_ctx(_result=None):
    return _LAST_CONTEXT


def stock():
    return EntityInstance(
        entity_id="SEC:CN:A:600519",
        entity_type_code="ENTITY_01_01",
        canonical_name="贵州茅台",
        identifiers={"security_code": "600519"},
        status="verified",
    )


class ResearchReportTests(unittest.TestCase):
    def test_rating_counts_and_consensus_eps(self):
        frame = pd.DataFrame(
            {
                "股票代码": ["600519", "600519", "600519"],
                "机构": ["A", "B", "C"],
                "东财评级": ["买入", "买入", "增持"],
                "日期": ["2026-09-01", "2026-09-21", "2026-08-15"],
                "2026-盈利预测-收益": [10.0, 12.0, 11.0],
                "2027-盈利预测-收益": [11.0, 13.0, None],
                "报告PDF链接": ["u1", "u2", "u3"],
            }
        )
        result = coverage.research_report_lookup(
            call("research_report_lookup", {"code": "600519"}, frames={"stock_research_report_em": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["rating_counts"], {"买入": 2, "增持": 1})
        self.assertEqual(result.data["consensus_eps"]["2026"], 11.0)
        self.assertEqual(result.data["consensus_eps"]["2027"], 12.0)
        self.assertEqual(result.data["latest_report_date"], "2026-09-21")

    def test_missing_code_is_empty(self):
        result = coverage.research_report_lookup(call("research_report_lookup", {}))
        self.assertEqual(result.status, "empty")


class AnnouncementTests(unittest.TestCase):
    def test_returns_links_and_filters_days(self):
        frame = pd.DataFrame(
            {
                "代码": ["600519", "600519"],
                "简称": ["贵州茅台", "贵州茅台"],
                "公告标题": ["半年报", "分红公告"],
                "公告时间": ["2026-08-15", "2026-05-10"],
                "公告链接": ["l1", "l2"],
            }
        )
        result = coverage.announcement_document_lookup(
            call(
                "announcement_document_lookup",
                {"code": "sh600519", "days": 30, "keyword": ""},
                frames={"stock_zh_a_disclosure_report_cninfo": frame},
            )
        )
        self.assertEqual(result.status, "ok")
        # 日期过滤由数据源完成，这里校验请求参数与链接透传。
        self.assertRegex(calls_ctx().calls[-1][1]["start_date"], r"^\d{8}$")
        self.assertEqual(result.data["stock_code"], "600519")
        self.assertEqual(result.data["count"], 2)


class OverseasQuoteTests(unittest.TestCase):
    def test_filters_by_days_and_normalizes_symbol(self):
        frame = pd.DataFrame(
            {
                "date": ["2026-10-20", "2026-10-21", "2026-10-22"],
                "open": [1.0, 2.0, 3.0],
                "high": [1.0, 2.0, 3.0],
                "low": [1.0, 2.0, 3.0],
                "close": [10.0, 11.0, 12.0],
                "volume": [100, 200, 300],
            }
        )
        result = coverage.overseas_quote_lookup(
            call(
                "overseas_quote_lookup",
                {"market": "美股", "code": "aapl", "days": 10},
                frames={"stock_us_daily": frame},
            )
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["symbol"], "aapl")
        self.assertEqual(calls_ctx().calls[-1][1]["symbol"], "AAPL")
        self.assertEqual(result.data["summary"]["points"], 3)

    def test_unknown_market_is_empty(self):
        result = coverage.overseas_quote_lookup(call("overseas_quote_lookup", {"market": "英股", "code": "X"}))
        self.assertEqual(result.status, "empty")


class MinuteBarTests(unittest.TestCase):
    def test_market_prefix_and_period(self):
        frame = pd.DataFrame(
            {
                "day": ["2026-10-27 09:35:00", "2026-10-27 09:40:00"],
                "open": [1.0, 2.0],
                "high": [1.0, 2.0],
                "low": [1.0, 2.0],
                "close": [10.0, 11.0],
                "volume": [100, 200],
            }
        )
        result = coverage.minute_bar_lookup(
            call(
                "minute_bar_lookup",
                {"minute_period": "5", "limit": 10},
                [stock()],
                {"stock_zh_a_minute": frame},
            )
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["period_minutes"], 5)
        self.assertEqual(calls_ctx().calls[-1][1]["symbol"], "sh600519")

    def test_non_six_digit_code_is_empty(self):
        result = coverage.minute_bar_lookup(
            call("minute_bar_lookup", {"code": "ABC"}, [stock()])
        )
        self.assertEqual(result.status, "empty")


class BondYieldTests(unittest.TestCase):
    def test_latest_date_curves_are_grouped(self):
        frame = pd.DataFrame(
            {
                "曲线名称": ["中债国债收益率曲线", "中债国开债收益率曲线", "中债国债收益率曲线"],
                "日期": ["2026-10-20", "2026-10-20", "2026-10-21"],
                "1年": [1.1, 1.3, 1.2],
                "10年": [2.1, 2.3, 2.2],
            }
        )
        result = coverage.bond_yield_curve_lookup(
            call("bond_yield_curve_lookup", {"days": 30}, frames={"bond_china_yield": frame})
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.data["latest_date"], "2026-10-21")
        self.assertEqual(len(result.data["latest"]), 1)
        self.assertIn("中债国债收益率曲线", result.data["curves"])


class ForexTests(unittest.TestCase):
    def test_source_failure_is_unavailable_not_fake_rates(self):
        result = coverage.forex_rate_lookup(
            call("forex_rate_lookup", {}, frames={"forex_spot_em": RuntimeError("blocked")})
        )
        self.assertEqual(result.status, "unavailable")


if __name__ == "__main__":
    unittest.main()
