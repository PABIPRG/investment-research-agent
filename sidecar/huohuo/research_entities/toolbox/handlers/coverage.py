# -*- coding: utf-8 -*-
"""卖方观点、公告正文链接、海外行情、汇率、分钟线、债券收益率与 IPO。

这些都是“查得到什么就说什么”的公开数据：研报评级是一致预期线索，不是
投资建议；港美股价格是当地货币，不能按 A 股口径比较；债券收益率曲线
按曲线名称区分国债、国开债与信用债，不能笼统说成“国债收益率”。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..context import records_from_frame
from ..contracts import ToolCall
from ..helpers import (
    date_window,
    empty,
    ok,
    param_code,
    param_name,
    series_summary,
    unavailable,
)


def _limit(call: ToolCall, default: int, maximum: int = 200) -> int:
    raw = call.params.get("limit")
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _code(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text or None


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-", "nan"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _matches(record: dict[str, Any], keyword: str | None, keys: tuple[str, ...]) -> bool:
    if not keyword:
        return True
    needle = keyword.strip()
    return any(needle in str(record.get(key) or "") for key in keys)


# ── 卖方研报 / 评级 / 一致预期 ──────────────────────────────────────

_RATING_KEYS = ("东财评级", "评级")


def research_report_lookup(call: ToolCall):
    code = _code(param_code(call, "code", "stock_code")) or param_name(call)
    if not code:
        return empty(
            call,
            reason="需要提供 6 位证券代码才能查询研报与一致预期。",
            source="akshare.stock_research_report_em",
        )
    frame = call.ctx.call_akshare(
        "stock_research_report_em", symbol=str(code), timeout=30
    )
    records = records_from_frame(frame, latest_first=False)
    if not records:
        return empty(
            call,
            reason=f"没有查询到 {code} 的卖方研报记录。",
            source="akshare.stock_research_report_em",
        )
    records.sort(key=lambda item: str(item.get("日期") or ""), reverse=True)

    rating_counts: dict[str, int] = {}
    for item in records:
        rating = next((str(item.get(key)) for key in _RATING_KEYS if item.get(key)), "")
        if rating:
            rating_counts[rating] = rating_counts.get(rating, 0) + 1

    consensus: dict[str, dict[str, float]] = {}
    for item in records:
        for key, value in item.items():
            if not key.endswith("-盈利预测-收益"):
                continue
            year = key.split("-")[0]
            number = _number(value)
            if number is None:
                continue
            bucket = consensus.setdefault(year, {"sum": 0.0, "count": 0})
            bucket["sum"] += number
            bucket["count"] += 1
    consensus_eps = {
        year: round(bucket["sum"] / bucket["count"], 4)
        for year, bucket in sorted(consensus.items())
        if bucket["count"]
    }

    institutions = sorted({str(item.get("机构")) for item in records if item.get("机构")})
    returned = records[: _limit(call, 50, maximum=200)]
    from ...report_documents import report_id
    returned=[{**r,'report_id':report_id(r.get('报告PDF链接'))} for r in returned]
    return ok(
        call,
        records=returned,
        data={
            "stock_code": code,
            "report_count": len(records),
            "returned": len(returned),
            "latest_report_date": str(records[0].get("日期")) if records else None,
            "rating_counts": rating_counts,
            "institution_count": len(institutions),
            "institutions": institutions[:20],
            "consensus_eps": consensus_eps,
        },
        source="akshare.stock_research_report_em",
        warnings=[
            "研报评级与盈利预测是卖方观点，不是事实；一致预期取同一股票最近 report_count 篇研报的算术均值，样本口径见返回记录。",
            "EPS 预测年度列由数据源直接给出，不同机构预测期可能不一致。",
        ],
    )


# ── 公告正文链接（巨潮）────────────────────────────────────────────

def announcement_document_lookup(call: ToolCall):
    code = _code(param_code(call, "code", "stock_code"))
    if not code:
        return empty(
            call,
            reason="需要提供 6 位证券代码才能查询公告清单。",
            source="akshare.stock_zh_a_disclosure_report_cninfo",
        )
    start, end = date_window(call, default_days=90)
    keyword = str(call.params.get("keyword") or "").strip()
    kwargs: dict[str, Any] = {
        "symbol": str(code),
        "market": "沪深京",
        "start_date": start,
        "end_date": end,
    }
    if keyword:
        kwargs["keyword"] = keyword
    frame = call.ctx.call_akshare(
        "stock_zh_a_disclosure_report_cninfo", timeout=45, **kwargs
    )
    records = records_from_frame(frame, latest_first=False)
    records.sort(key=lambda item: str(item.get("公告时间") or ""), reverse=True)
    returned = records[: _limit(call, 50, maximum=200)]
    if not returned:
        return empty(
            call,
            reason=f"{start}~{end} 没有查询到 {code} 的公告。",
            source="akshare.stock_zh_a_disclosure_report_cninfo",
        )
    return ok(
        call,
        records=returned,
        data={
            "stock_code": code,
            "start_date": start,
            "end_date": end,
            "keyword": keyword or None,
            "count": len(returned),
        },
        source="akshare.stock_zh_a_disclosure_report_cninfo",
        warnings=[
            "返回巨潮公告清单与原文链接；工具不解析 PDF 正文，细节需打开链接核对。",
        ],
    )


# ── 业绩快报 ───────────────────────────────────────────────────────

def _latest_report_period(today: date) -> str:
    boundaries = ((3, 31), (6, 30), (9, 30), (12, 31))
    for month, day in reversed(boundaries):
        candidate = date(today.year, month, day)
        if candidate <= today:
            return candidate.strftime("%Y%m%d")
    return date(today.year - 1, 12, 31).strftime("%Y%m%d")


def performance_express_lookup(call: ToolCall):
    report_period = str(
        call.params.get("report_period") or _latest_report_period(call.ctx.today())
    )
    frame = call.ctx.call_akshare(
        "stock_yjkb_em", date=report_period, timeout=60
    )
    records = records_from_frame(frame, latest_first=False)
    keyword = str(call.params.get("keyword") or "").strip()
    if keyword:
        records = [
            item
            for item in records
            if _matches(item, keyword, ("股票简称", "股票代码", "所处行业"))
        ]
    records.sort(
        key=lambda item: _number(item.get("净利润-同比增长")) or float("-inf"),
        reverse=True,
    )
    returned = records[: _limit(call, 100, maximum=500)]
    if not returned:
        return empty(
            call,
            reason=f"{report_period} 没有查询到业绩快报" + (f"（关键词：{keyword}）" if keyword else "") + "。",
            source="akshare.stock_yjkb_em",
        )
    return ok(
        call,
        records=returned,
        data={
            "report_period": report_period,
            "keyword": keyword or None,
            "matched": len(returned),
        },
        source="akshare.stock_yjkb_em",
        warnings=[
            "业绩快报是公司初步核算数，可能随后续定期报告调整；不是审计数，也不代表全部公司都已披露。",
        ],
    )


# ── 港股 / 美股行情 ────────────────────────────────────────────────

_OVERSEAS_MARKETS = {"港股": "stock_hk_daily", "美股": "stock_us_daily"}


def overseas_quote_lookup(call: ToolCall):
    market = str(call.params.get("market") or "")
    function_name = _OVERSEAS_MARKETS.get(market)
    if function_name is None:
        return empty(
            call,
            reason=f"只支持港股与美股，收到：{market or '未提供'}",
            source="akshare",
        )
    code = _code(param_code(call, "code")) or param_name(call)
    if not code:
        return empty(
            call,
            reason=f"需要提供{market}代码（港股如 00700，美股如 AAPL）。",
            source=f"akshare.{function_name}",
        )
    frame = call.ctx.call_akshare(
        function_name, symbol=str(code).upper() if market == "美股" else str(code), timeout=45
    )
    records = records_from_frame(frame, latest_first=True)
    if not records:
        return empty(
            call,
            reason=f"没有查询到 {code} 的{market}行情。",
            source=f"akshare.{function_name}",
        )
    days = int(call.params.get("days") or 250)
    cutoff = call.ctx.today().toordinal() - days
    filtered = []
    for item in records:
        raw = str(item.get("date") or "")
        try:
            ordinal = date.fromisoformat(raw[:10]).toordinal()
        except ValueError:
            filtered.append(item)
            continue
        if ordinal >= cutoff:
            filtered.append(item)
    rows = filtered[: _limit(call, 250, maximum=1000)]
    summary = series_summary(filtered, date_key="date", value_key="close")
    return ok(
        call,
        records=rows,
        data={
            "market": market,
            "symbol": code,
            "days": days,
            "summary": summary,
        },
        source=f"akshare.{function_name}",
        warnings=[
            f"{market}价格为当地货币计价，并可能与 A 股交易时段、复权口径不同，不能直接与 A 股涨跌幅比较。",
            "数据来自新浪历史行情，延迟以来源为准。",
        ],
    )


# ── 人民币汇率 ────────────────────────────────────────────────────

def forex_rate_lookup(call: ToolCall):
    try:
        frame = call.ctx.call_akshare("forex_spot_em", timeout=30)
    except Exception as exc:  # 来源被阻断或代理失败时不能给出任何汇率数字。
        return unavailable(
            call,
            f"汇率快照来源当前不可用：{type(exc).__name__}",
            source="akshare.forex_spot_em",
        )
    records = records_from_frame(frame, latest_first=False)
    keyword = str(call.params.get("keyword") or "").strip()
    if keyword:
        records = [item for item in records if _matches(item, keyword, ("名称", "代码"))]
    returned = records[: _limit(call, 50, maximum=200)]
    if not returned:
        return unavailable(
            call,
            "汇率快照来源当前不可用或没有匹配项；请稍后重试，不能用其他市场数据代替。",
            source="akshare.forex_spot_em",
        )
    return ok(
        call,
        records=returned,
        data={"keyword": keyword or None, "count": len(returned)},
        source="akshare.forex_spot_em",
        warnings=["这是外汇即期快照，不是银行结售汇牌价，也不是远期汇率。"],
    )


# ── A 股分钟线 ────────────────────────────────────────────────────

_MINUTE_PERIODS = {"1", "5", "15", "30", "60"}


def _market_symbol(code: str) -> str:
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


def minute_bar_lookup(call: ToolCall):
    code = _code(param_code(call, "code", "security_code"))
    if not code or len(code) != 6:
        return empty(
            call,
            reason="分钟线需要 6 位 A 股证券代码；指数与港股不支持。",
            source="akshare.stock_zh_a_minute",
        )
    period = str(call.params.get("minute_period") or "5")
    if period not in _MINUTE_PERIODS:
        return empty(
            call,
            reason=f"不支持的分钟周期：{period}",
            source="akshare.stock_zh_a_minute",
        )
    frame = call.ctx.call_akshare(
        "stock_zh_a_minute", symbol=_market_symbol(code), period=period, adjust="", timeout=30
    )
    records = records_from_frame(frame, latest_first=True)
    rows = records[: _limit(call, 240, maximum=1000)]
    if not rows:
        return empty(
            call,
            reason=f"没有查询到 {code} 的 {period} 分钟线。",
            source="akshare.stock_zh_a_minute",
        )
    return ok(
        call,
        records=rows,
        data={
            "security_code": code,
            "period_minutes": int(period),
            "summary": series_summary(records, date_key="day", value_key="close"),
        },
        source="akshare.stock_zh_a_minute",
        warnings=[
            "分钟线来自新浪，通常只覆盖最近几个交易日；未做复权，除权日前后不可直接连续比较。",
        ],
    )


# ── 债券收益率曲线 ────────────────────────────────────────────────

def bond_yield_curve_lookup(call: ToolCall):
    start, end = date_window(call, default_days=30)
    frame = call.ctx.call_akshare(
        "bond_china_yield", start_date=start, end_date=end, timeout=45
    )
    records = records_from_frame(frame, latest_first=False)
    if not records:
        return empty(
            call,
            reason=f"{start}~{end} 没有债券收益率曲线数据。",
            source="akshare.bond_china_yield",
        )
    records.sort(key=lambda item: (str(item.get("日期") or ""), str(item.get("曲线名称") or "")))
    curves = sorted({str(item.get("曲线名称")) for item in records if item.get("曲线名称")})
    latest_date = max(str(item.get("日期") or "") for item in records)
    latest = [item for item in records if str(item.get("日期") or "") == latest_date]
    returned = records[-_limit(call, 120, maximum=500) :]
    return ok(
        call,
        records=returned,
        data={
            "start_date": start,
            "end_date": end,
            "curves": curves,
            "latest_date": latest_date,
            "latest": latest,
        },
        source="akshare.bond_china_yield",
        warnings=[
            "曲线名称区分国债、国开债、中短期票据等，引用时必须写明曲线名称与期限。",
            "收益率单位为百分比；数据来自中债口径的公开镜像，报告期末可能缺值。",
        ],
    )


# ── IPO 发行信息 ──────────────────────────────────────────────────

_IPO_COLUMNS = (
    "招股公告日期",
    "上网发行日期",
    "上市日期",
    "发行价格",
    "总发行数量",
    "摊薄发行市盈率",
    "募集资金净额",
    "主承销商",
)


def ipo_detail_lookup(call: ToolCall):
    code = _code(param_code(call, "code", "stock_code"))
    if not code:
        return empty(
            call,
            reason="需要提供 6 位股票代码才能查询 IPO 发行信息。",
            source="akshare.stock_ipo_summary_cninfo",
        )
    frame = call.ctx.call_akshare("stock_ipo_summary_cninfo", symbol=str(code), timeout=30)
    records = records_from_frame(frame, latest_first=False)
    if not records:
        return empty(
            call,
            reason=f"没有查询到 {code} 的 IPO 发行记录（可能尚未发行或不在该库）。",
            source="akshare.stock_ipo_summary_cninfo",
        )
    return ok(
        call,
        records=records[: _limit(call, 10, maximum=20)],
        data={
            "stock_code": code,
            "columns": list(_IPO_COLUMNS),
        },
        source="akshare.stock_ipo_summary_cninfo",
        warnings=["发行数据为历史发行信息，不复权、不代表当前估值。"],
    )
