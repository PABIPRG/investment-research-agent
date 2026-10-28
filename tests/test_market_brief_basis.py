"""盘前/盘后来源时间与日历准入回归。"""
import copy
import unittest
from datetime import date, datetime

from huohuo.market.brief_basis import validate_brief_basis
from huohuo.market.calendar import CalendarUnavailable
from huohuo.market.contracts import UNITS, envelope
from huohuo.market.quotes import INDICES


class KnownCalendar:
    def is_trading_day(self, day):
        if not date(2026, 10, 22) <= day <= date(2026, 10, 28):
            raise CalendarUnavailable()
        return day in {date(2026, 10, 23), date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)}


def fixture(period="post", stamp="2026-10-27T07:34:00+00:00"):
    def row(code, index=False):
        units = dict(UNITS)
        if index:
            units.update(price="point", previous_close="point")
        return {"code": code, "price": 100, "previous_close": 99, "pct_change": 1.01,
                "as_of": stamp, "time_known": True, "stale": True, "units": units}
    quotes = envelope("eastmoney", {"items": [row("600519")], "requested_codes": ["600519"]}, as_of=stamp)
    indices = envelope("eastmoney", {"items": [row(c, True) for c in INDICES]}, as_of=stamp)
    quotes["stale"] = indices["stale"] = True
    news = envelope("sina+cls", {"items": []}, status="empty")
    raw = envelope("market_brief", {"period": period, "quotes": quotes, "indices": indices, "news": news}, as_of=stamp)
    raw.update(stale=True, cache="live")
    return raw


class BriefBasisTests(unittest.TestCase):
    def check(self, raw=None, period="post", now="2026-10-27T17:00:00+08:00", calendar=None):
        return validate_brief_basis(raw or fixture(period), period, calendar or KnownCalendar(), now=datetime.fromisoformat(now))

    def test_post_accepts_same_day_close_and_retains_original_stale(self):
        raw = fixture()
        before = copy.deepcopy(raw)
        result = self.check(raw)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["basis"], "closing_reference")
        self.assertEqual(result["reference_date"], "2026-10-27")
        self.assertTrue(result["raw_stale"])
        self.assertEqual(raw, before)

    def test_pre_uses_previous_actual_trading_day_across_weekend(self):
        result = self.check(fixture("pre", "2026-10-23T07:30:00+00:00"), "pre", "2026-10-26T08:30:00+08:00")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reference_date"], "2026-10-23")

    def test_today_intraday_previous_close_and_future_time_fail(self):
        for stamp in ("2026-10-27T06:59:59+00:00", "2026-10-26T07:01:00+00:00", "2026-10-27T10:00:00+00:00"):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.check(fixture(stamp=stamp))["status"], "unavailable")

    def test_source_failed_cache_cannot_be_promoted(self):
        for section in (None, "quotes", "indices", "news"):
            raw = fixture()
            target = raw if section is None else raw["data"][section]
            target["cache"] = "stale"
            self.assertEqual(self.check(raw)["status"], "unavailable")

    def test_news_successful_empty_is_valid_but_partial_failed_or_stale_is_not(self):
        self.assertEqual(self.check()["status"], "ok")
        for change in ({"complete": False}, {"status": "unavailable"}, {"stale": True}):
            raw = fixture()
            raw["data"]["news"].update(change)
            self.assertEqual(self.check(raw)["status"], "unavailable")

    def test_missing_index_unknown_timestamp_and_wrong_units_fail(self):
        for change in ("missing", "time", "unit", "nan"):
            raw = fixture()
            if change == "missing":
                raw["data"]["indices"]["data"]["items"].pop()
            else:
                row = raw["data"]["quotes"]["data"]["items"][0]
                if change == "time":
                    row.update(time_known=False, as_of=None)
                elif change == "unit":
                    row["units"]["price"] = "point"
                else:
                    row["price"] = float("nan")
            self.assertEqual(self.check(raw)["status"], "unavailable")

    def test_calendar_unknown_holiday_and_outside_time_window_fail(self):
        for now in ("2026-10-25T17:00:00+08:00", "2026-10-27T14:59:59+08:00", "2027-01-01T17:00:00+08:00"):
            self.assertEqual(self.check(now=now)["status"], "unavailable")
        self.assertEqual(self.check(fixture("pre"), "pre", "2026-10-27T09:30:00+08:00")["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
