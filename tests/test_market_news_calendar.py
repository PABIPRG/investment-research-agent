import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from huohuo.market.calendar import CalendarUnavailable, SOURCE_URL, TradingCalendar, fetch_calendar
from huohuo.market.news import fetch_news, item, safe_url, sina_stock
from huohuo.market.technical import fetch_technical

NOW = "2026-10-27T02:00:00+00:00"


class NewsTests(unittest.TestCase):
    def news(self, published="2026-10-27 10:00:00", url="https://example.org/news/1"):
        return item("<b>公告标题</b>", "正文", url, published, "原始媒体", provider="eastmoney", source_url="https://source.example.org")

    def test_id_is_stable_across_observation_and_changes_with_publication(self):
        with patch("huohuo.market.news.utc_now", return_value=NOW):
            a = self.news()
        with patch("huohuo.market.news.utc_now", return_value="2026-10-28T02:00:00+00:00"):
            b = self.news()
        self.assertEqual(a["id"], b["id"])
        self.assertNotEqual(a["observed_at"], b["observed_at"])
        self.assertNotEqual(a["id"], self.news("2026-10-27 11:00:00")["id"])
        self.assertEqual(a["source"], "原始媒体")
        self.assertEqual(a["title"], "公告标题")

    def test_unknown_date_and_unsafe_links_are_not_fabricated(self):
        a = self.news("10:00", "javascript:alert(1)")
        self.assertIsNone(a["published_at"])
        self.assertIsNone(a["url"])
        self.assertFalse(a["time_known"])
        self.assertEqual(safe_url("https://user:pass@example.org/x"), "")

    def test_partial_flash_is_not_empty_and_missing_source_is_visible(self):
        with patch("huohuo.market.news.sina", return_value=[self.news()]), patch("huohuo.market.news.cls", side_effect=TimeoutError):
            result = fetch_news({"limit": 2})
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["complete"])
        self.assertEqual(result["source"], "sina")
        self.assertTrue(result["warnings"])

    def test_directed_news_uses_sina_stock_when_eastmoney_search_breaks(self):
        with patch("huohuo.market.news.directed", side_effect=ValueError("invalid directed news response")), \
                patch("huohuo.market.news.sina_stock", return_value=[self.news()]) as stock:
            result = fetch_news({"limit": 3, "code": "600879"})
        stock.assert_called_once_with("600879", 3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["code"], "600879")
        self.assertEqual(result["source"], "sina")
        self.assertFalse(result["complete"])
        self.assertTrue(any("eastmoney" in warning for warning in result["warnings"]))

    def test_sina_stock_keeps_only_dated_a_share_items(self):
        page = ('<div class="datelist"><ul>&nbsp;2026-10-29&nbsp;10:29&nbsp;&nbsp;'
                "<a target='_blank' href='https://example.org/a'>航天电子获融资买入</a> <br>"
                "&nbsp;&nbsp;&nbsp;&nbsp;2026-10-28&nbsp;08:01&nbsp;&nbsp;"
                "<a target='_blank' href='https://example.org/b'>低轨卫星发射</a> <br></ul></div>")
        with patch("huohuo.market.news.read", return_value=page):
            rows = sina_stock("600879", 5)
        self.assertEqual([row["title"] for row in rows], ["航天电子获融资买入", "低轨卫星发射"])
        self.assertEqual(rows[0]["code"], "600879")
        self.assertTrue(rows[0]["published_at"].startswith("2026-10-29"))
        with self.assertRaises(ValueError):
            sina_stock("920001", 5)

    def test_all_failed_differs_from_verified_empty(self):
        with patch("huohuo.market.news.sina", side_effect=TimeoutError), patch("huohuo.market.news.cls", side_effect=TimeoutError):
            self.assertEqual(fetch_news({"limit": 2})["status"], "unavailable")
        with patch("huohuo.market.news.sina", return_value=[]), patch("huohuo.market.news.cls", return_value=[]):
            result = fetch_news({"limit": 2})
            self.assertEqual(result["status"], "empty")
            self.assertTrue(result["complete"])


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.doc = {"source": "sina", "source_url": SOURCE_URL, "observed_at": NOW,
                    "coverage_start": "2026-09-30", "coverage_end": "2026-10-09",
                    "trading_days": ["2026-09-30", "2026-10-08", "2026-10-09"]}

    def test_holiday_is_false_even_on_weekday_and_unknown_is_exception(self):
        calendar = TradingCalendar(loader=lambda: self.doc, now=lambda: NOW)
        calendar.refresh()
        self.assertFalse(calendar.is_trading_day(date(2026, 10, 1)))
        self.assertTrue(calendar.is_trading_day(date(2026, 10, 8)))
        with self.assertRaises(CalendarUnavailable):
            calendar.is_trading_day(date(2027, 1, 1))

    def test_failure_never_falls_back_to_weekday(self):
        def fail():
            raise TimeoutError()
        calendar = TradingCalendar(loader=fail, now=lambda: NOW)
        with self.assertRaises(CalendarUnavailable):
            calendar.is_trading_day(date(2026, 10, 27))

    def test_lookup_never_calls_network_and_refresh_is_explicit(self):
        from unittest.mock import Mock
        loader = Mock(return_value=self.doc)
        calendar = TradingCalendar(loader=loader, now=lambda: NOW)
        with self.assertRaises(CalendarUnavailable):
            calendar.is_trading_day(date(2026, 10, 8))
        loader.assert_not_called()
        calendar.refresh()
        self.assertTrue(calendar.is_trading_day(date(2026, 10, 8)))
        calendar.refresh()
        self.assertEqual(loader.call_count, 1)

    def test_instance_cache_survives_restart_but_expires(self):
        with tempfile.TemporaryDirectory(prefix="market-calendar-test-") as folder:
            path = Path(folder) / "calendar.json"
            calendar = TradingCalendar(path, lambda: self.doc, now=lambda: NOW)
            calendar.refresh()
            self.assertTrue(calendar.is_trading_day(date(2026, 10, 8)))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            def fail():
                raise TimeoutError()
            restarted = TradingCalendar(path, fail, now=lambda: "2026-10-28T02:00:01+00:00")
            self.assertTrue(restarted.is_trading_day(date(2026, 10, 8)))
            expired = TradingCalendar(path, fail, now=lambda: "2026-11-05T02:00:00+00:00")
            with self.assertRaises(CalendarUnavailable):
                expired.is_trading_day(date(2026, 10, 8))

    def test_corrupt_cache_and_script_response_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="market-calendar-test-") as folder:
            path = Path(folder) / "calendar.json"
            path.write_text('{"trading_days": []}')
            calendar = TradingCalendar(path, loader=lambda: {}, now=lambda: NOW)
            with self.assertRaises(CalendarUnavailable):
                calendar.is_trading_day(date(2026, 10, 27))
        with patch("huohuo.market.calendar.read", return_value='var datelist="ABCD"; arbitraryCode();'):
            with self.assertRaises(CalendarUnavailable):
                fetch_calendar()


class TechnicalTests(unittest.TestCase):
    def bars(self):
        from datetime import timedelta
        return [{"date": (date(2026, 8, 1) + timedelta(days=i)).isoformat(), "open": 10 + i,
                 "close": 10.5 + i, "high": 11 + i, "low": 9 + i, "volume": 1000 + i, "amount": 10000 + i}
                for i in range(60)]

    def test_original_indicators_and_units_are_exposed(self):
        with patch("huohuo.market.technical.eastmoney", return_value=self.bars()):
            result = fetch_technical({"code": "600519", "lookback": 60})
        self.assertTrue(result["complete"])
        self.assertIsNotNone(result["data"]["indicators"]["rsi"]["rsi14"])
        self.assertIsNotNone(result["data"]["indicators"]["macd"]["hist"])
        self.assertEqual(result["data"]["adjustment"], "qfq")
        json.dumps(result, allow_nan=False)

    def test_invalid_bars_and_volume_unknown_make_result_partial(self):
        bars = self.bars()
        bars[-1]["close"] = None
        bars[-2]["volume"] = None
        with patch("huohuo.market.technical.eastmoney", return_value=bars):
            result = fetch_technical({"code": "600519", "lookback": 60})
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["data"]["bars"]), 59)
        self.assertIsNone(result["data"]["indicators"]["pattern"]["vol_ratio"])
        json.dumps(result, allow_nan=False)

    def test_sina_fallback_never_claims_forward_adjustment_or_estimated_amount(self):
        bars = self.bars()
        for bar in bars:
            bar["amount"] = None
        with patch("huohuo.market.technical.eastmoney", side_effect=TimeoutError), patch("huohuo.market.technical.sina", return_value=bars):
            result = fetch_technical({"code": "600519", "lookback": 60})
        self.assertFalse(result["complete"])
        self.assertEqual(result["data"]["adjustment"], "unadjusted")
        self.assertIsNone(result["data"]["bars"][0]["amount"])


if __name__ == "__main__":
    unittest.main()
