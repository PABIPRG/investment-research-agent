"""盘前/盘后来源时间与日历准入回归。"""
import copy
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from huohuo.market.brief_basis import validate_brief_basis
from huohuo.market.calendar import CalendarUnavailable
from huohuo.market.contracts import CN, UNITS, envelope, source_time
from huohuo.market.provider import _pre_close
from huohuo.market.quotes import INDICES, _kline, daily_close


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


def daily_close_fixture(reference="2026-10-26", period="pre"):
    """前一交易日日线收盘口径的资料包：只精确到交易日。"""
    raw = fixture(period, source_time(reference + " 00:00:00"))
    for name in ("quotes", "indices"):
        for row in raw["data"][name]["data"]["items"]:
            row.update(price_basis="daily_close", time_precision="date")
    return raw


class DailyCloseBasisTests(unittest.TestCase):
    def check(self, raw, now="2026-10-27T08:45:00+08:00"):
        return validate_brief_basis(raw, "pre", KnownCalendar(), now=datetime.fromisoformat(now))

    def test_pre_accepts_daily_close_labelled_with_date_precision(self):
        result = self.check(daily_close_fixture())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reference_date"], "2026-10-26")
        self.assertTrue(any("日线" in warning for warning in result["warnings"]))

    def test_daily_close_requires_precision_marker_and_reference_date(self):
        raw = daily_close_fixture()
        raw["data"]["quotes"]["data"]["items"][0].pop("time_precision")
        self.assertEqual(self.check(raw)["status"], "unavailable")

        raw = daily_close_fixture()
        stale = source_time("2026-10-23 00:00:00")
        raw["data"]["quotes"]["data"]["items"][0]["as_of"] = stale
        self.assertEqual(self.check(raw)["status"], "unavailable")

        # 没有 daily_close 标注的 00:00 时间仍按盘中快照口径拒绝。
        raw = daily_close_fixture()
        raw["data"]["quotes"]["data"]["items"][0].pop("price_basis")
        self.assertEqual(self.check(raw)["status"], "unavailable")


def bars(*pairs):
    return [{"date": day, "close": close, "volume": 100, "amount": 1e8} for day, close in pairs]


class DailyCloseTests(unittest.TestCase):
    def test_close_uses_last_completed_bar_and_labels_date_precision(self):
        with patch("huohuo.market.quotes._kline", return_value=bars(("2026-10-27", 10.0), ("2026-10-28", 10.5))):
            rows = daily_close(["600879"], names={"600879": "航天电子"})
        row = rows[0]
        self.assertEqual((row["price"], row["previous_close"], row["pct_change"]), (10.5, 10.0, 5.0))
        self.assertEqual((row["price_basis"], row["time_precision"], row["time_known"]), ("daily_close", "date", True))
        self.assertEqual(row["name"], "航天电子")
        self.assertEqual(row["units"]["price"], "CNY/share")
        self.assertIsNone(row["volume_ratio"])
        self.assertEqual(row["as_of"], source_time("2026-10-28 00:00:00"))

    def test_index_rows_use_points_and_skip_unknown_series(self):
        with patch("huohuo.market.quotes._kline", side_effect=lambda code, indices: bars(("2026-10-27", 3000.0), ("2026-10-28", 3030.0)) if code == "000001" else []):
            rows = daily_close(list(INDICES), indices=True)
        self.assertEqual([row["code"] for row in rows], ["000001"])
        self.assertEqual(rows[0]["name"], "上证指数")
        self.assertEqual(rows[0]["units"]["price"], "point")
        self.assertIsNone(rows[0]["volume"])

    def test_kline_drops_unclosed_today_bar(self):
        today = datetime.now(CN).date()
        payload = {"data": {"klines": [
            f"{(today - timedelta(days=2)).isoformat()},0,10.0,0,0,100,1000000",
            f"{(today - timedelta(days=1)).isoformat()},0,10.5,0,0,110,1100000",
            f"{today.isoformat()},0,9.9,0,0,10,100000",
        ]}}
        with patch("huohuo.market.quotes.read_json", return_value=payload):
            result = _kline("600879", False)
        self.assertEqual([bar["date"] for bar in result], [(today - timedelta(days=2)).isoformat(),
                                                           (today - timedelta(days=1)).isoformat()])

    def test_both_sources_empty_yields_no_rows(self):
        with patch("huohuo.market.quotes.read_json", side_effect=TimeoutError):
            self.assertEqual(daily_close(["600879"]), [])


class PreCloseFallbackTests(unittest.TestCase):
    def section(self, stamp):
        row = {"code": "600879", "name": "航天电子", "price": 10.5, "previous_close": 10.4,
               "pct_change": 0.96, "as_of": stamp, "time_known": True, "units": dict(UNITS)}
        return envelope("eastmoney", {"items": [row], "requested_codes": ["600879"]}, as_of=stamp)

    def test_live_previous_close_rows_are_kept(self):
        today = datetime.now(CN).date()
        live = self.section(source_time((today - timedelta(days=1)).isoformat() + " 15:00:00"))
        with patch("huohuo.market.provider.daily_close") as fallback:
            self.assertIs(_pre_close(live, ["600879"]), live)
        fallback.assert_not_called()

    def test_intraday_snapshot_is_replaced_by_dated_close(self):
        today = datetime.now(CN).date()
        live = self.section(source_time(today.isoformat() + " 09:15:00"))
        closed = {"code": "600879", "name": "航天电子", "price": 10.5, "previous_close": 10.0,
                  "pct_change": 5.0, "as_of": source_time((today - timedelta(days=1)).isoformat() + " 00:00:00"),
                  "time_known": True, "units": dict(UNITS), "price_basis": "daily_close", "time_precision": "date"}
        with patch("huohuo.market.provider.daily_close", return_value=[closed]):
            result = _pre_close(live, ["600879"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["data"]["items"][0]["price_basis"], "daily_close")
        self.assertTrue(any("日线" in warning for warning in result["warnings"]))

    def test_failed_fallback_keeps_original_section_instead_of_fabricating(self):
        today = datetime.now(CN).date()
        live = self.section(source_time(today.isoformat() + " 09:15:00"))
        with patch("huohuo.market.provider.daily_close", return_value=[]):
            self.assertIs(_pre_close(live, ["600879"]), live)

    def test_brief_wires_fallback_for_pre_only(self):
        from huohuo.market import provider
        today = datetime.now(CN).date()
        live = self.section(source_time(today.isoformat() + " 09:15:00"))
        closed = {"code": "600879", "name": "航天电子", "price": 10.5, "previous_close": 10.0,
                  "pct_change": 5.0, "as_of": source_time((today - timedelta(days=1)).isoformat() + " 00:00:00"),
                  "time_known": True, "units": dict(UNITS), "source": "eastmoney:kline",
                  "price_basis": "daily_close", "time_precision": "date"}
        news = envelope("sina", {"items": []}, status="empty")
        with patch.object(provider, "fetch_quotes", return_value=live), \
                patch.object(provider, "fetch_news", return_value=news), \
                patch.object(provider, "daily_close", return_value=[closed]):
            pre = provider.brief({"codes": ["600879"], "period": "pre", "include_slow": False})
            post = provider.brief({"codes": ["600879"], "period": "post", "include_slow": False})
        self.assertEqual(pre["data"]["quotes"]["source"], "eastmoney:kline")
        self.assertIs(post["data"]["quotes"], live)


if __name__ == "__main__":
    unittest.main()
