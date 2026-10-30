"""盘前/盘后收盘参考准入；保留原报价 stale，不宣称实时。"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from .calendar import CalendarUnavailable
from .contracts import CN, number, source_time
from .quotes import INDICES


def validate_brief_basis(raw, period, calendar, *, now: datetime | None = None):
    """仅读给定资料和日历内存快照，不做刷新、网络或业务写入。

    成功仅证明可作为对应交易日的收盘参考。供 Sources 在保留 raw 的前提下
    记录 basis/reference_date/as_of；不清除 raw.stale、不授予触发或通知资格。
    """
    raw = raw if isinstance(raw, dict) else {}
    base = {"status": "unavailable", "basis": "closing_reference", "as_of": None,
            "reference_date": None, "period": period, "raw_stale": bool(raw.get("stale")), "warnings": []}

    def fail(reason, message):
        return {**base, "reason": reason, "warnings": [message]}

    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return fail("time_unknown", "收盘参考校验需要带时区的当前时间")
    local = now.astimezone(CN)
    if period not in {"pre", "post"}:
        return fail("period_invalid", "需明确盘前或盘后资料口径")
    if (period == "post" and local.time() < time(15)) or (period == "pre" and local.time() >= time(9, 30)):
        return fail("outside_brief_window", "尚不在盘后收盘参考时段，或已过盘前资料时段")
    try:
        if not calendar.is_trading_day(local.date()):
            return fail("not_trading_day", "当前日期不是已确认交易日")
        reference = local.date()
        if period == "pre":
            for offset in range(1, 32):
                candidate = local.date() - timedelta(days=offset)
                if calendar.is_trading_day(candidate):
                    reference = candidate
                    break
            else:
                return fail("previous_trading_day_unknown", "未在已核对区间找到前一交易日")
    except (CalendarUnavailable, ValueError, TypeError):
        return fail("calendar_unavailable", "交易日历未就绪或不覆盖所需日期，不能猜测收盘基准")
    base["reference_date"] = reference.isoformat()
    if raw.get("status") != "ok" or raw.get("complete") is not True or raw.get("cache") == "stale":
        return fail("brief_incomplete", "资料包不完整或为来源失败时的旧缓存，不能确认为有效简报")
    data = raw.get("data")
    if not isinstance(data, dict) or data.get("period") != period:
        return fail("brief_period_mismatch", "资料包与请求的盘前/盘后口径不一致")
    news = data.get("news")
    if not isinstance(news, dict) or news.get("status") not in {"ok", "empty"} or news.get("complete") is not True:
        return fail("news_incomplete", "新闻资料未完整读取；查询失败不能解释成没有新消息")
    if news.get("cache") == "stale" or news.get("stale"):
        return fail("news_stale", "新闻为过期或来源失败缓存，不能作为本次简报资料")
    news_data = news.get("data")
    if not isinstance(news_data, dict) or not isinstance(news_data.get("items"), list):
        return fail("news_invalid", "新闻资料格式缺失")
    if news.get("status") == "empty" and news_data["items"]:
        return fail("news_invalid", "新闻空结果与条目内容矛盾")
    stamps, dated_close_used = [], False
    for name in ("quotes", "indices"):
        section = data.get(name)
        if not isinstance(section, dict) or section.get("status") != "ok" or section.get("complete") is not True:
            return fail("quote_incomplete", "个股或指数资料不完整，不能确认为收盘参考")
        if section.get("cache") == "stale":
            return fail("quote_failed_cache", "个股或指数返回来源失败旧缓存，不能提升为有效收盘参考")
        section_data = section.get("data")
        items = section_data.get("items") if isinstance(section_data, dict) else None
        if not isinstance(items, list) or not items:
            return fail("quote_missing", "个股或指数资料缺少报价条目")
        if not all(isinstance(row, dict) for row in items):
            return fail("quote_invalid", "报价条目格式不合法")
        codes = [row.get("code") for row in items]
        expected = list(INDICES) if name == "indices" else section_data.get("requested_codes")
        if len(set(codes)) != len(codes) or (expected and set(codes) != set(expected)):
            return fail("quote_subject_missing", "报价缺少约定证券或四个基准指数，不能确认为完整参考")
        for row in items:
            stamp = source_time(row.get("as_of"))
            if row.get("time_known") is not True or stamp is None:
                return fail("quote_time_unknown", "报价来源时间未知，不能以采集时间代替收盘时间")
            source_local = datetime.fromisoformat(stamp).astimezone(CN)
            if row.get("price_basis") == "daily_close":
                # 日线收盘只标到交易日（日期精度），不满足“15:00 之后”的盘中快照口径。
                if row.get("time_precision") != "date":
                    return fail("quote_basis_unknown", "日线收盘口径必须明确标注日期精度")
                if source_local.date() != reference or source_local.time() != time(0):
                    return fail("quote_not_reference_close", "日线收盘日期不是所需交易日")
                dated_close_used = True
            elif source_local.date() != reference or source_local.time() < time(15):
                return fail("quote_not_reference_close", "报价不是所需交易日 15:00 之后的收盘时点")
            if source_local > local:
                return fail("quote_time_future", "报价来源时间晚于校验时点")
            price, previous = number(row.get("price")), number(row.get("previous_close"))
            if price is None or price <= 0 or previous is None or previous <= 0 or number(row.get("pct_change")) is None:
                return fail("quote_value_unknown", "收盘参考所需价格或涨跌幅缺失")
            unit = "point" if name == "indices" else "CNY/share"
            units = row.get("units", {})
            if units.get("price") != unit or units.get("previous_close") != unit or units.get("pct_change") != "%":
                return fail("quote_unit_unknown", "报价单位不匹配，不能混用指数点数与股票价格")
            stamps.append(stamp)
    note = f"采用 {reference.isoformat()} 收盘参考；保留原报价过期标记，不表示盘中实时行情"
    if dated_close_used:
        note += "；部分或全部价格为日线收盘，仅精确到交易日"
    return {**base, "status": "ok", "as_of": max(stamps), "warnings": [note]}
