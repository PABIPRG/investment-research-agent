# -*- coding: utf-8 -*-
"""业绩预告、市场估值与个股估值类工具。

估值分位只描述“当前值在所选历史区间中的相对位置”，不是买卖信号；
负利润时市盈率可能为负或缺失，必须保留这一限制。
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from ...errors import SourceUnavailable
from ..context import records_from_frame
from ..contracts import ToolCall
from ..helpers import (
    empty,
    entity_code,
    first_entity,
    ok,
    param_name,
    series_summary,
    unavailable,
)


def _limit(call: ToolCall, default: int, maximum: int = 100) -> int:
    raw = call.params.get("limit")
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-", "nan"):
            return None
        if isinstance(value, str) and value.endswith("%"):
            value = value[:-1]
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(records: list[dict[str, Any]], key: str, latest: float | None) -> float | None:
    if latest is None:
        return None
    values = [item for item in (_number(row.get(key)) for row in records) if item is not None]
    if not values:
        return None
    return round(sum(1 for item in values if item <= latest) / len(values) * 100, 2)


# ── 业绩预告 ────────────────────────────────────────────────────────

_FORECAST_TYPES = ("全部", "预增", "预减", "扭亏", "首亏", "续盈", "续亏", "略增", "略减", "不确定")
_NEGATIVE_FORECAST_TYPES = {"预减", "首亏", "续亏", "略减"}


def _latest_report_period(today: date) -> str:
    """返回最近一个已结束季度的报告期（YYYYMMDD）。"""

    boundaries = ((3, 31), (6, 30), (9, 30), (12, 31))
    for month, day in reversed(boundaries):
        candidate = date(today.year, month, day)
        if candidate <= today:
            return candidate.strftime("%Y%m%d")
    return date(today.year - 1, 12, 31).strftime("%Y%m%d")


def performance_forecast_lookup(call: ToolCall):
    report_period = str(
        call.params.get("report_period") or _latest_report_period(call.ctx.today())
    )
    forecast_type = str(call.params.get("forecast_type") or "全部")
    if forecast_type not in _FORECAST_TYPES:
        return empty(
            call,
            reason=f"不支持的预告类型“{forecast_type}”，可选：{'、'.join(_FORECAST_TYPES)}。",
            source="akshare.stock_yjyg_em",
        )
    try:
        frame = call.ctx.call_akshare("stock_yjyg_em", date=report_period, timeout=30)
        records = records_from_frame(frame, latest_first=False)
    except SourceUnavailable as exc:
        return unavailable(
            call, f"业绩预告数据不可用：{type(exc).__name__}", source="akshare.stock_yjyg_em"
        )
    if not records:
        return empty(
            call,
            reason=f"报告期 {report_period} 没有业绩预告记录。",
            source="akshare.stock_yjyg_em",
        )
    type_counts = Counter(str(item.get("预告类型") or "未分类") for item in records)
    if forecast_type != "全部":
        records = [
            item for item in records if str(item.get("预告类型") or "") == forecast_type
        ]
    keyword = param_name(call)
    if keyword:
        records = [
            item
            for item in records
            if keyword in str(item.get("股票简称") or "")
            or keyword in str(item.get("股票代码") or "")
        ]
    if not records:
        return empty(
            call,
            reason=f"报告期 {report_period} 没有符合筛选条件的业绩预告。",
            source="akshare.stock_yjyg_em",
        )

    ascending = forecast_type in _NEGATIVE_FORECAST_TYPES
    ranked_records = sorted(
        records,
        key=lambda item: (
            _number(item.get("业绩变动幅度")) is None,
            _number(item.get("业绩变动幅度")) or 0.0,
        ),
        reverse=not ascending,
    )
    # 缺失值在 reverse 排序下会排到最前，稳定地放回末尾。
    present = [
        item for item in ranked_records if _number(item.get("业绩变动幅度")) is not None
    ]
    missing = [
        item for item in ranked_records if _number(item.get("业绩变动幅度")) is None
    ]
    ranked_records = present + missing
    selected = ranked_records[: _limit(call, 30, maximum=100)]
    return ok(
        call,
        records=selected,
        data={
            "report_period": report_period,
            "forecast_type": forecast_type,
            "matched": len(records),
            "type_counts": dict(sorted(type_counts.items())),
            "sorted_by": "业绩变动幅度",
            "sort_direction": "asc" if ascending else "desc",
        },
        source="akshare.stock_yjyg_em",
        warnings=[
            "业绩预告是上市公司自行披露的区间预计，最终财务数据可能不同；"
            "业绩变动幅度口径以公告原文为准。",
            "预告类型与幅度均由数据源给出，本工具不做二次推断。",
        ],
    )


# ── 市场估值 ────────────────────────────────────────────────────────

_INDEX_PE_SYMBOLS = {
    "沪深300": "沪深300",
    "上证50": "上证50",
    "中证500": "中证500",
    "中证1000": "中证1000",
    "中证800": "中证800",
}


def market_valuation_lookup(call: ToolCall):
    index_name = str(call.params.get("index_name") or "全A")
    limit = _limit(call, 60, maximum=240)
    if index_name == "全A":
        try:
            frame = call.ctx.call_akshare("stock_a_ttm_lyr", timeout=30)
            full = records_from_frame(frame, latest_first=True)
            rows = full[:limit]
        except SourceUnavailable as exc:
            return unavailable(
                call, f"全 A 估值数据不可用：{type(exc).__name__}", source="akshare.stock_a_ttm_lyr"
            )
        if not rows:
            return empty(
                call, reason="全 A 估值序列为空。", source="akshare.stock_a_ttm_lyr"
            )
        latest = full[0]
        data = {
            "index_name": "全A",
            "latest": {
                "date": latest.get("date"),
                "中位PE_TTM": latest.get("middlePETTM"),
                "平均PE_TTM": latest.get("averagePETTM"),
                "中位PE_LYR": latest.get("middlePELYR"),
                "平均PE_LYR": latest.get("averagePELYR"),
                "收盘": latest.get("close"),
                "全历史中位PE_TTM分位": latest.get("quantileInAllHistoryMiddlePeTtm"),
                "近十年中位PE_TTM分位": latest.get("quantileInRecent10YearsMiddlePeTtm"),
            },
            "percentile_note": "分位字段为 0–1 的小数，0.5 表示处于历史中位。",
            "summary": series_summary(full, value_key="middlePETTM", date_key="date"),
        }
        source = "akshare.stock_a_ttm_lyr"
    else:
        symbol = _INDEX_PE_SYMBOLS.get(index_name)
        if symbol is None:
            return empty(
                call,
                reason=f"不支持的估值指数“{index_name}”，可选：全A、{'、'.join(_INDEX_PE_SYMBOLS)}。",
                source="akshare.stock_index_pe_lg",
            )
        try:
            frame = call.ctx.call_akshare("stock_index_pe_lg", symbol=symbol, timeout=30)
            full = records_from_frame(frame, latest_first=True)
            rows = full[:limit]
        except SourceUnavailable as exc:
            return unavailable(
                call,
                f"{index_name}估值数据不可用：{type(exc).__name__}",
                source="akshare.stock_index_pe_lg",
            )
        if not rows:
            return empty(
                call, reason=f"{index_name}估值序列为空。", source="akshare.stock_index_pe_lg"
            )
        latest_pe = _number(full[0].get("滚动市盈率"))
        data = {
            "index_name": index_name,
            "latest": full[0],
            "percentile": {
                "field": "滚动市盈率",
                "window_points": len(full),
                "percentile": _percentile(full, "滚动市盈率", latest_pe),
                "note": "分位按数据源返回的全部历史样本计算，不是近期窗口。",
            },
            "summary": series_summary(full, value_key="滚动市盈率", date_key="日期"),
        }
        source = "akshare.stock_index_pe_lg"

    return ok(
        call,
        records=rows,
        data=data,
        source=source,
        warnings=[
            "估值分位只描述当前值在所选历史区间中的位置，不预测未来收益。",
            "乐咕乐股口径的市盈率分为静态/滚动、整体/中位数，引用时必须说明具体字段。",
        ],
    )


# ── 个股估值 ────────────────────────────────────────────────────────

_VALUATION_INDICATORS = ("总市值", "市盈率(TTM)", "市盈率(静)", "市净率", "市现率")
_VALUATION_PERIODS = ("近一年", "近三年", "近五年", "近十年", "全部")


def stock_valuation_lookup(call: ToolCall):
    entity = first_entity(call, "ENTITY_01_01")
    code = entity_code(entity)
    if not code:
        return empty(
            call,
            reason="没有可识别的 A 股代码，无法查询个股估值。",
            source="akshare.stock_zh_valuation_baidu",
        )
    indicator = str(call.params.get("valuation_indicator") or "市盈率(TTM)")
    if indicator not in _VALUATION_INDICATORS:
        return empty(
            call,
            reason=f"不支持的估值指标“{indicator}”，可选：{'、'.join(_VALUATION_INDICATORS)}。",
            source="akshare.stock_zh_valuation_baidu",
        )
    period = str(call.params.get("valuation_period") or "近一年")
    if period not in _VALUATION_PERIODS:
        return empty(
            call,
            reason=f"不支持的区间“{period}”，可选：{'、'.join(_VALUATION_PERIODS)}。",
            source="akshare.stock_zh_valuation_baidu",
        )
    try:
        frame = call.ctx.call_akshare(
            "stock_zh_valuation_baidu",
            symbol=code,
            indicator=indicator,
            period=period,
            timeout=30,
        )
        full = records_from_frame(frame, latest_first=True)
        rows = full[: _limit(call, 500, maximum=2000)]
    except SourceUnavailable as exc:
        return unavailable(
            call,
            f"个股估值数据不可用：{type(exc).__name__}",
            source="akshare.stock_zh_valuation_baidu",
        )
    if not rows:
        return empty(
            call,
            reason=f"{code} 在{period}内没有{indicator}序列。",
            source="akshare.stock_zh_valuation_baidu",
        )
    latest_value = _number(full[0].get("value"))
    return ok(
        call,
        records=rows,
        data={
            "security_code": code,
            "indicator": indicator,
            "period": period,
            "latest": {"date": full[0].get("date"), "value": latest_value},
            "percentile": {
                "window_points": len(full),
                "percentile": _percentile(full, "value", latest_value),
                "note": f"分位按所选区间（{period}）全部样本计算，不是全历史分位。",
            },
            "summary": series_summary(full, value_key="value", date_key="date"),
        },
        source="akshare.stock_zh_valuation_baidu",
        warnings=[
            "估值序列来自百度股市通，数值单位与指标口径以数据源页面为准，本工具不做换算。",
            "历史分位只描述所选区间内的相对位置；负利润时市盈率可能为负或缺失。",
        ],
    )
