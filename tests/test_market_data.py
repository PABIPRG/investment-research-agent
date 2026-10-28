"""行情查询边界与失败/缓存语义，不依赖外部网络。"""
import copy
import json
import subprocess
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from huohuo.contracts import Invalid
from huohuo.market import MarketData
from huohuo.market.contracts import envelope, number, source_time, validate
from huohuo.market.quotes import fetch_quotes, parse_eastmoney, sina
from huohuo.market.scan import fetch_scan
from huohuo.market.service import isolated_provider

NOW = "2026-10-27T02:00:00+00:00"
STAMP = "2026-10-27T01:59:30+00:00"


def quote_result():
    row = parse_eastmoney({"f12": "600519", "f14": "贵州茅台", "f2": 100, "f18": 99,
                          "f3": 1.01, "f5": 20, "f6": 200000, "f8": 0.1, "f10": 1.2,
                          "f124": datetime.fromisoformat(STAMP).timestamp()})
    return envelope("eastmoney", {"items": [row]}, as_of=STAMP)


class MarketContractTests(unittest.TestCase):
    def test_requests_require_explicit_scope_and_bounded_numeric_inputs(self):
        invalid = [{}, {"operation": "scan"}, {"operation": "quotes", "codes": []},
                   {"operation": "quotes", "codes": ["http://internal"]},
                   {"operation": "technical", "code": "600519", "lookback": 10000},
                   {"operation": "news", "limit": True},
                   {"operation": "scan", "kind": "amount", "min_amount_yi": float("nan")},
                   {"operation": "news", "url": "http://internal"},
                   {"operation": "brief", "codes": ["600519"]}]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(Invalid):
                validate(request)
        self.assertEqual(validate({"operation": "quotes", "codes": ["600519", "600519"]})["codes"], ["600519"])

    def test_unknown_numbers_and_times_are_not_zero_or_observed_time(self):
        for value in (None, "-", "nan", "Infinity", float("inf"), True):
            self.assertIsNone(number(value))
        self.assertEqual(number(0), 0)
        self.assertIsNone(source_time("10:30:00"))
        self.assertIsNone(source_time(float("nan")))
        self.assertEqual(source_time("2026-10-27 10:00:00"), NOW)

    def test_eastmoney_volume_lots_are_normalized_to_shares(self):
        row = quote_result()["data"]["items"][0]
        self.assertEqual(row["volume"], 2000)
        self.assertEqual(row["units"]["volume"], "share")
        self.assertEqual(row["as_of"], STAMP)
        self.assertNotEqual(row["observed_at"], row["as_of"])

    def test_sina_keeps_missing_fields_unknown_and_does_not_replace_zero_price(self):
        fields = ["测试", "1", "10", "0", "1", "1", "0", "0", "100", "1000"] + ["0"] * 20 + ["2026-10-27", "10:00:00"]
        with patch("huohuo.market.quotes.read", return_value='var hq_str_sh600519="' + ",".join(fields) + '";'):
            row = sina(["600519"])[0]
        self.assertIsNone(row["price"])
        self.assertIsNone(row["volume_ratio"])
        self.assertEqual(row["as_of"], NOW)

    def test_partial_quotes_keep_missing_codes_and_unknown_fields(self):
        row = quote_result()["data"]["items"][0]
        with patch("huohuo.market.quotes.eastmoney", return_value=[row]), patch("huohuo.market.quotes.sina", side_effect=TimeoutError):
            result = fetch_quotes(["600519", "000001"])
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["complete"])
        self.assertEqual(result["data"]["missing_codes"], ["000001"])

    def test_volume_ratio_has_no_fake_sina_fallback(self):
        with patch("huohuo.market.scan.eastmoney", side_effect=TimeoutError), patch("huohuo.market.scan.sina") as fallback:
            result = fetch_scan(validate({"operation": "scan", "kind": "volume_ratio"}))
        self.assertEqual(result["status"], "unavailable")
        fallback.assert_not_called()

    def test_limit_scan_is_marked_candidate_and_not_complete(self):
        row = quote_result()["data"]["items"][0]
        row["pct_change"] = 10
        with patch("huohuo.market.scan.eastmoney", return_value=[row]):
            result = fetch_scan(validate({"operation": "scan", "kind": "limit", "limit": 2}))
        self.assertFalse(result["complete"])
        self.assertEqual(result["data"]["items"][0]["limit_candidate"], "up")


class MarketServiceTests(unittest.TestCase):
    def setUp(self):
        self.elapsed = 0
        self.provider_calls = 0
        self.fail = False
        def provider(request):
            self.provider_calls += 1
            if self.fail:
                raise TimeoutError()
            return quote_result()
        self.service = MarketData(provider, clock=lambda: self.elapsed, now=lambda: NOW)
        self.request = {"operation": "quotes", "codes": ["600519"]}

    def test_live_and_fresh_cache_preserve_source_time_and_return_copies(self):
        result = self.service.query(self.request)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["stale"])
        result["data"]["items"].clear()
        cached = self.service.query(self.request)
        self.assertEqual(cached["cache"], "fresh")
        self.assertEqual(len(cached["data"]["items"]), 1)
        self.assertEqual(cached["as_of"], STAMP)
        self.assertEqual(self.provider_calls, 1)

    def test_timeout_returns_bounded_stale_cache_without_promoting_time(self):
        result = self.service.query(self.request)
        self.elapsed = 20
        self.fail = True
        stale = self.service.query(self.request)
        self.assertTrue(stale["stale"])
        self.assertFalse(stale["complete"])
        self.assertEqual(stale["observed_at"], result["observed_at"])
        self.assertEqual(stale["as_of"], STAMP)
        self.elapsed = 601
        self.assertEqual(self.service.query(self.request)["status"], "unavailable")

    def test_failure_without_cache_is_not_empty_or_no_change(self):
        self.fail = True
        result = self.service.query(self.request)
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["complete"])
        self.assertEqual(result["data"], {})

    def test_nonfinite_is_partial_and_strict_json_serializable(self):
        raw = quote_result()
        raw["data"]["items"][0]["volume_ratio"] = float("nan")
        service = MarketData(lambda _: raw, now=lambda: NOW)
        result = service.query(self.request)
        self.assertIsNone(result["data"]["items"][0]["volume_ratio"])
        self.assertFalse(result["complete"])
        json.dumps(result, allow_nan=False)

    def test_old_and_unknown_quote_times_are_never_current_evidence(self):
        for stamp in (None, "2026-10-26T01:59:30+00:00", "2026-10-28T01:59:30+00:00"):
            raw = quote_result()
            raw["data"]["items"][0]["as_of"] = stamp
            service = MarketData(lambda _: copy.deepcopy(raw), now=lambda: NOW)
            result = service.query(self.request)
            if stamp:
                self.assertTrue(result["stale"])
            else:
                self.assertFalse(result["complete"])
                self.assertFalse(result["data"]["items"][0]["time_known"])

    def test_capacity_and_singleflight_return_explicit_busy(self):
        self.service._capacity.acquire()
        self.service._capacity.acquire()
        self.service._capacity.acquire()
        self.service._capacity.acquire()
        result = self.service.query(self.request)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.provider_calls, 0)

    def test_brief_does_not_hide_old_component_times(self):
        q = quote_result()
        q["data"]["items"][0]["as_of"] = "2026-10-26T02:00:00+00:00"
        raw = envelope("market_brief", {"quotes": q, "indices": q, "news": envelope("sina", {"items": []}, status="empty")})
        result = MarketData(lambda _: raw, now=lambda: NOW).query({"operation": "brief", "codes": ["600519"], "period": "post"})
        self.assertTrue(result["stale"])
        self.assertTrue(result["data"]["indices"]["stale"])

    def test_actual_subprocess_deadline_terminates_early(self):
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            isolated_provider({"operation": "news"}, timeout=0.00001)
        self.assertLess(time.monotonic() - started, 2)


if __name__ == "__main__":
    unittest.main()
