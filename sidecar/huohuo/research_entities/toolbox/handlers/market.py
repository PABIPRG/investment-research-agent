# -*- coding: utf-8 -*-
"""全市场行情、板块排行、市场情绪、快讯与 ETF 榜单类工具。

这些工具回答的是“今天市场/板块怎么样”，不绑定具体确认实体，因此属于
``tool_contracts.GLOBAL``。它们只读取公开行情快照，不构成投资建议；
所有排序、涨跌与资金数值均来自数据源原始字段，本层不重算收益。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ...errors import SourceUnavailable
from ..context import records_from_frame
from ..contracts import ToolCall
from ..helpers import empty, ok, param_name, unavailable
from ..trading_calendar import calendar_for


def _limit(call: ToolCall, default: int, maximum: int = 100) -> int:
    raw = call.params.get("limit")
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        if isinstance(value, str) and value.endswith("%"):
            value = value[:-1]
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_records(records: list[dict[str, Any]], field: str, *, reverse: bool) -> list[dict[str, Any]]:
    """按数值字段排序；缺失值始终排在末尾。"""

    def key(record: dict[str, Any]) -> tuple[int, float]:
        value = _number(record.get(field))
        return (1, 0.0) if value is None else (0, value)

    ordered = sorted(records, key=key, reverse=reverse)
    if reverse:
        # reverse=True 会把缺失值排到最前；稳定地移回末尾。
        present = [item for item in ordered if _number(item.get(field)) is not None]
        missing = [item for item in ordered if _number(item.get(field)) is None]
        ordered = present + missing
    return ordered


def _rank(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**record, "排名": index} for index, record in enumerate(records, start=1)]


# ── 板块排行 ────────────────────────────────────────────────────────

# 同花顺行业一览表；概念板块用同花顺概念资金流（含涨跌幅与净额）。
_SECTOR_SORT_FIELDS = {
    "行业": {
        "涨幅": ("涨跌幅", True),
        "跌幅": ("涨跌幅", False),
        "净流入": ("净流入", True),
        "上涨家数": ("上涨家数", True),
        "成交额": ("总成交额", True),
    },
    "概念": {
        "涨幅": ("涨跌幅", True),
        "跌幅": ("涨跌幅", False),
        "净流入": ("净流入", True),
    },
}


def _industry_overview(call: ToolCall) -> tuple[list[dict[str, Any]], str]:
    frame = call.ctx.call_akshare("stock_board_industry_summary_ths", timeout=60)
    records = records_from_frame(frame, latest_first=False)
    normalized = []
    for item in records:
        row = dict(item)
        row["板块"] = row.pop("板块", row.pop("行业", None))
        normalized.append(row)
    return normalized, "akshare.stock_board_industry_summary_ths"


def _concept_overview(call: ToolCall) -> tuple[list[dict[str, Any]], str]:
    frame = call.ctx.call_akshare(
        "stock_fund_flow_concept", symbol="即时", timeout=45
    )
    records = records_from_frame(frame, latest_first=False)
    normalized = []
    for item in records:
        row = dict(item)
        row["板块"] = row.pop("行业", None)
        row["涨跌幅"] = row.pop("行业-涨跌幅", None)
        row["净流入"] = row.pop("净额", None)
        normalized.append(row)
    return normalized, "akshare.stock_fund_flow_concept(即时)"


def sector_ranking_lookup(call: ToolCall):
    sector_type = str(call.params.get("sector_type") or "行业")
    sorts = _SECTOR_SORT_FIELDS.get(sector_type)
    if sorts is None:
        return empty(
            call,
            reason=f"不支持的板块类型“{sector_type}”，可选：行业、概念。",
            source="akshare 同花顺板块",
        )
    sort_by = str(call.params.get("sector_sort") or "涨幅")
    sort_spec = sorts.get(sort_by)
    if sort_spec is None:
        return empty(
            call,
            reason=(
                f"{sector_type}板块不支持按“{sort_by}”排序，可选："
                f"{'、'.join(sorts)}。"
            ),
            source="akshare 同花顺板块",
        )
    try:
        if sector_type == "行业":
            records, source = _industry_overview(call)
        else:
            records, source = _concept_overview(call)
    except SourceUnavailable as exc:
        return unavailable(call, f"{sector_type}板块排行数据不可用：{type(exc).__name__}", source="akshare 同花顺板块")
    if not records:
        return empty(call, reason=f"{sector_type}板块没有返回数据。", source=source)
    field, reverse = sort_spec
    ranked = _rank(_sort_records(records, field, reverse=reverse)[: _limit(call, 20)])
    return ok(
        call,
        records=ranked,
        data={
            "sector_type": sector_type,
            "sort": sort_by,
            "sort_field": field,
            "board_count": len(records),
        },
        source=source,
        warnings=[
            "板块分类为同花顺口径，与申万行业分类不完全一致。",
            "行情为最近交易日/盘中快照；成交额、净流入单位以同花顺页面为准，不做换算。",
        ],
    )


# ── 板块资金流排行 ──────────────────────────────────────────────────

_FLOW_TYPES = ("行业资金流", "概念资金流", "地域资金流")
_FLOW_INDICATORS = ("今日", "5日", "10日")
_THS_INDICATORS = {"今日": "即时", "5日": "5日排行", "10日": "10日排行"}


def _normalize_ths_flow(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in records:
        row = dict(item)
        row["板块"] = row.pop("行业", None)
        row["涨跌幅"] = row.pop("行业-涨跌幅", row.pop("阶段涨跌幅", None))
        row["净流入"] = row.pop("净额", None)
        normalized.append(row)
    return normalized


def sector_fund_flow_lookup(call: ToolCall):
    sector_type = str(call.params.get("flow_type") or "行业资金流")
    if sector_type not in _FLOW_TYPES:
        return empty(
            call,
            reason=f"不支持的板块类型“{sector_type}”，可选：{'、'.join(_FLOW_TYPES)}。",
            source="akshare 同花顺/东方财富资金流",
        )
    indicator = str(call.params.get("indicator") or "今日")
    if indicator not in _FLOW_INDICATORS:
        return empty(
            call,
            reason=f"不支持的统计周期“{indicator}”，可选：{'、'.join(_FLOW_INDICATORS)}。",
            source="akshare 同花顺/东方财富资金流",
        )
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    if sector_type == "行业资金流":
        frame = call.ctx.call_akshare(
            "stock_fund_flow_industry", symbol=_THS_INDICATORS[indicator], timeout=45
        )
        records = _normalize_ths_flow(records_from_frame(frame, latest_first=False))
        source = "akshare.stock_fund_flow_industry"
        warnings.append("同花顺行业资金流按板块汇总，资金单位以同花顺页面为准。")
    elif sector_type == "概念资金流":
        frame = call.ctx.call_akshare(
            "stock_fund_flow_concept", symbol=_THS_INDICATORS[indicator], timeout=45
        )
        records = _normalize_ths_flow(records_from_frame(frame, latest_first=False))
        source = "akshare.stock_fund_flow_concept"
        warnings.append("同花顺概念资金流按概念板块汇总，概念之间可能存在成分重叠。")
    else:
        # 地域板块没有同花顺资金流接口，退回东方财富；口径与上面两类不同。
        frame = call.ctx.call_akshare(
            "stock_sector_fund_flow_rank",
            indicator=indicator,
            sector_type="地域资金流",
            timeout=60,
        )
        records = records_from_frame(frame, latest_first=False)
        source = "akshare.stock_sector_fund_flow_rank(地域资金流)"
        warnings.append("地域资金流来自东方财富，字段与同花顺行业/概念口径不同。")

    if not records:
        return empty(
            call,
            reason=f"{sector_type}（{indicator}）没有返回资金流排行。",
            source=source,
        )
    if sector_type == "地域资金流":
        ranked = records[: _limit(call, 20)]
    else:
        field = "净流入"
        ranked = _rank(_sort_records(records, field, reverse=True)[: _limit(call, 20)])
    return ok(
        call,
        records=ranked,
        data={
            "sector_type": sector_type,
            "indicator": indicator,
            "sorted_by": "净流入" if sector_type != "地域资金流" else f"{indicator}主力净流入-净额",
        },
        source=source,
        warnings=warnings
        + ["主力/净流入按数据源的大单口径统计，不等于全部成交资金。"],
    )


# ── 市场概览 ────────────────────────────────────────────────────────

_MAIN_INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000300": "沪深300",
    "sh000016": "上证50",
    "sh000905": "中证500",
    "sh000852": "中证1000",
    "sh000688": "科创50",
    "sz399905": "中证500(深)",
}


def _index_snapshot(call: ToolCall) -> list[dict[str, Any]]:
    frame = call.ctx.call_akshare("stock_zh_index_spot_sina", timeout=45)
    rows = records_from_frame(frame, latest_first=False)
    selected: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("代码") or "").lower()
        if code in _MAIN_INDEX_CODES:
            selected.append(row)
    return selected


def _breadth_from_spot(call: ToolCall) -> dict[str, Any]:
    frame = call.ctx.call_akshare("stock_zh_a_spot_em", timeout=20)
    rows = records_from_frame(frame, latest_first=False)
    if not rows:raise SourceUnavailable("全 A 行情样本为空，不能统计市场广度")
    up = down = flat = 0
    for row in rows:
        change = _number(row.get("涨跌幅"))
        if change is None:
            continue
        if change > 0:
            up += 1
        elif change < 0:
            down += 1
        else:
            flat += 1
    return {"上涨家数": up, "下跌家数": down, "平盘家数": flat, "统计口径": "全 A 实时行情涨跌幅统计"}


def market_overview_lookup(call: ToolCall):
    data: dict[str, Any] = {}
    warnings: list[str] = []
    sources: list[str] = []
    records: list[dict[str, Any]] = []

    try:
        index_rows = _index_snapshot(call)
        if index_rows:
            records = index_rows
            data["indices"] = index_rows
            sources.append("akshare.stock_zh_index_spot_sina")
        else:
            warnings.append("指数快照中没有匹配到主要宽基指数。")
    except SourceUnavailable as exc:
        warnings.append(f"指数快照不可用：{type(exc).__name__}")

    activity: dict[str, Any] | None = None
    try:
        frame = call.ctx.call_akshare("stock_market_activity_legu", timeout=12)
        raw_activity: dict[str, Any] = {}
        for row in records_from_frame(frame, latest_first=False):
            item = str(row.get("item") or "").strip()
            if item:
                raw_activity[item] = row.get("value")
        if raw_activity:
            activity = raw_activity
            sources.append("akshare.stock_market_activity_legu")
        else:
            warnings.append("赚钱效应接口返回空表。")
    except SourceUnavailable as exc:
        warnings.append(f"赚钱效应（涨跌家数/涨停跌停）不可用：{type(exc).__name__}")

    if activity is None:
        try:
            activity = _breadth_from_spot(call)
            sources.append("akshare.stock_zh_a_spot_em（涨跌家数统计）")
            warnings.append("涨跌家数由全 A 实时行情按涨跌幅符号统计，未单独判定涨停/跌停。")
        except SourceUnavailable as exc:
            warnings.append(f"全 A 行情涨跌家数统计也不可用：{type(exc).__name__}")

    if activity is not None:
        data["market_activity"] = activity

    if not sources:
        return unavailable(
            call,
            "市场概览的全部数据源均不可用，未生成任何替代数值。",
            source="none",
        )
    kwargs: dict[str, Any] = {
        "data": data,
        "source": " + ".join(sources),
        "warnings": warnings
        + ["市场概览为最近交易日/盘中快照；不同来源的统计时点可能略有差异。"],
    }
    if records:
        kwargs["records"] = records
    return ok(call, **kwargs)


# ── 个股人气榜 ──────────────────────────────────────────────────────

_HOT_SOURCES = {
    "人气榜": ("stock_hot_rank_em", "东方财富人气榜"),
    "飙升榜": ("stock_hot_up_em", "东方财富飙升榜"),
}


def hot_stock_rank_lookup(call: ToolCall):
    rank_type = str(call.params.get("rank_type") or "人气榜")
    selected = _HOT_SOURCES.get(rank_type)
    if selected is None:
        return empty(
            call,
            reason=f"不支持的榜单“{rank_type}”，可选：人气榜、飙升榜。",
            source="akshare.stock_hot_*",
        )
    function, display = selected
    frame = call.ctx.call_akshare(function, timeout=30)
    records = records_from_frame(frame, latest_first=False, limit=_limit(call, 30))
    if not records:
        return empty(call, reason=f"{display}没有返回数据。", source=f"akshare.{function}")
    return ok(
        call,
        records=records,
        data={"rank_type": rank_type},
        source=f"akshare.{function}",
        warnings=["人气/飙升榜是东方财富股吧用户关注度指标，不是资金流或基本面指标。"],
    )


# ── 涨停板股池 ──────────────────────────────────────────────────────

_POOL_SOURCES = {
    "涨停": ("stock_zt_pool_em", "涨停股池"),
    "跌停": ("stock_zt_pool_dtgc_em", "跌停股池"),
    "强势": ("stock_zt_pool_strong_em", "强势股池"),
    "炸板": ("stock_zt_pool_zbgc_em", "炸板股池"),
}


def limit_pool_lookup(call: ToolCall):
    pool_type = str(call.params.get("pool_type") or "涨停")
    selected = _POOL_SOURCES.get(pool_type)
    if selected is None:
        return empty(
            call,
            reason=f"不支持的股池“{pool_type}”，可选：{'、'.join(_POOL_SOURCES)}。",
            source="akshare.stock_zt_pool_*",
        )
    function, display = selected
    raw_days = call.params.get("days")
    try:
        days = max(1, min(int(raw_days) if raw_days is not None else 3, 5))
    except (TypeError, ValueError):
        days = 3

    calendar = calendar_for(call.ctx)
    latest = calendar.latest_on_or_before(call.ctx.today())
    cursor: date = latest
    attempted: list[str] = []
    frame = None
    chosen: date | None = None
    for _ in range(days):
        attempted.append(cursor.strftime("%Y%m%d"))
        current = call.ctx.call_akshare(function, date=cursor.strftime("%Y%m%d"), timeout=30)
        if current is not None and len(current):
            frame = current
            chosen = cursor
            break
        cursor = calendar.previous_trading_day(cursor)

    if frame is None or chosen is None:
        return empty(
            call,
            reason=f"最近 {days} 个交易日没有{display}数据（已尝试 {', '.join(attempted)}）。",
            source=f"akshare.{function}",
        )
    records = records_from_frame(frame, latest_first=False, limit=_limit(call, 50))
    warnings = ["涨停/跌停股池按交易日收盘后的交易所口径统计；盘中数据可能不完整。"]
    if chosen != latest:
        warnings.append(
            f"最新可用的{display}日期为 {chosen.isoformat()}，最近交易日 {latest.isoformat()} 尚无数据。"
        )
    return ok(
        call,
        records=records,
        data={
            "pool_type": pool_type,
            "trade_date": chosen.isoformat(),
            "total": len(frame),
            "attempted_dates": attempted,
        },
        source=f"akshare.{function}",
        warnings=warnings,
    )


# ── 市场快讯 ────────────────────────────────────────────────────────

_NEWS_SOURCES = ("全部", "东方财富", "财联社")


def market_news_lookup(call: ToolCall):
    source_choice = str(call.params.get("news_source") or "全部")
    if source_choice not in _NEWS_SOURCES:
        return empty(
            call,
            reason=f"不支持的快讯来源“{source_choice}”，可选：{'、'.join(_NEWS_SOURCES)}。",
            source="akshare.stock_info_global_*",
        )
    keyword = param_name(call) or ""
    limit = _limit(call, 30, maximum=50)
    records: list[dict[str, Any]] = []
    sources: list[str] = []
    warnings: list[str] = []

    def matches(text: str) -> bool:
        return not keyword or keyword in text

    if source_choice in ("全部", "东方财富"):
        try:
            frame = call.ctx.call_akshare("stock_info_global_em", timeout=30)
            for item in records_from_frame(frame, latest_first=False, limit=200):
                title = str(item.get("标题") or "").strip()
                summary = str(item.get("摘要") or "").strip()
                if not matches(title) and not matches(summary):
                    continue
                records.append(
                    {
                        "标题": title,
                        "内容": summary[:500],
                        "发布时间": item.get("发布时间"),
                        "链接": item.get("链接"),
                        "来源": "东方财富快讯",
                    }
                )
            sources.append("akshare.stock_info_global_em")
        except SourceUnavailable as exc:
            warnings.append(f"东方财富快讯不可用：{type(exc).__name__}")

    if source_choice in ("全部", "财联社"):
        try:
            frame = call.ctx.call_akshare("stock_info_global_cls", symbol="全部", timeout=12)
            for item in records_from_frame(frame, latest_first=True, limit=200):
                title = str(item.get("标题") or "").strip()
                content = str(item.get("内容") or "").strip()
                if not matches(title) and not matches(content):
                    continue
                records.append(
                    {
                        "标题": title,
                        "内容": content[:500],
                        "发布日期": item.get("发布日期"),
                        "发布时间": item.get("发布时间"),
                        "来源": "财联社电报",
                    }
                )
            sources.append("akshare.stock_info_global_cls")
        except SourceUnavailable as exc:
            warnings.append(f"财联社电报不可用：{type(exc).__name__}")

    # 两家来源可能转载同一标题；按标题/内容去重，保留先出现的一条。
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in records:
        key_text = str(item.get("标题") or item.get("内容") or "")[:80]
        if not key_text or key_text in seen:
            continue
        seen.add(key_text)
        deduped.append(item)
    if not sources:
        return unavailable(call, "请求的快讯来源均不可用，不能认定没有新闻", source="market_news")
    if not deduped:
        reason = (
            f"近期公开快讯中没有检索到“{keyword}”。" if keyword else "快讯来源没有返回数据。"
        )
        return empty(call, reason=reason, source=" + ".join(sources) or "none")

    return ok(
        call,
        records=deduped[:limit],
        data={"keyword": keyword or None, "searched_sources": sources},
        source=" + ".join(sources),
        warnings=warnings
        + ["快讯是未经核实的新闻摘要，只能作为线索；引用前应核对原始报道或公告。"],
    )


# ── ETF 排行 ────────────────────────────────────────────────────────

_ETF_SORTS = {
    "涨幅": ("涨跌幅", True),
    "跌幅": ("涨跌幅", False),
    "成交额": ("成交额", True),
    "成交量": ("成交量", True),
}

_ETF_FIELDS = (
    "代码",
    "名称",
    "最新价",
    "涨跌幅",
    "成交额",
    "成交量",
    "昨收",
    "今开",
    "最高",
    "最低",
)


def etf_ranking_lookup(call: ToolCall):
    sort_by = str(call.params.get("etf_sort") or "成交额")
    sort_spec = _ETF_SORTS.get(sort_by)
    if sort_spec is None:
        return empty(
            call,
            reason=f"不支持的排序“{sort_by}”，可选：{'、'.join(_ETF_SORTS)}。",
            source="akshare.fund_etf_category_sina",
        )
    field, reverse = sort_spec
    keyword = param_name(call) or ""
    frame = call.ctx.call_akshare("fund_etf_category_sina", symbol="ETF基金", timeout=45)
    records = records_from_frame(frame, latest_first=False)
    if keyword:
        records = [
            item
            for item in records
            if keyword in str(item.get("名称") or "") or keyword in str(item.get("代码") or "")
        ]
        if not records:
            return empty(
                call,
                reason=f"ETF 列表中未找到名称或代码包含“{keyword}”的记录。",
                source="akshare.fund_etf_category_sina",
            )
    ranked = _rank(
        _sort_records(records, field, reverse=reverse)[: _limit(call, 20, maximum=50)]
    )
    trimmed = [
        {key: item[key] for key in _ETF_FIELDS if key in item} | {"排名": item["排名"]}
        for item in ranked
    ]
    return ok(
        call,
        records=trimmed,
        data={
            "sort": sort_by,
            "sort_field": field,
            "matched_count": len(records),
        },
        source="akshare.fund_etf_category_sina",
        warnings=[
            "ETF 行情为新浪盘中快照；成交额单位为数据源原始单位（通常为元）。",
            "该榜单只含场内 ETF 行情，不含基金净值、折溢价与资金流字段。",
        ],
    )
