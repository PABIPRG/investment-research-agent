# -*- coding: utf-8 -*-
"""工具 ID → 处理器映射。

注册表是唯一的事实来源：``registry.tools`` 描述能力，
本模块决定哪些能力在本进程真正可执行。
"""

from __future__ import annotations

from typing import Callable

from ..registry.tools import TOOL_REGISTRY
from .contracts import ToolCall
from .handlers import bond, coverage, equity, evolution, fund_index, local, macro, market, service, valuation
from .handlers import report_document

Handler = Callable[[ToolCall], object]

HANDLERS: dict[str, Handler] = {
    'research_report_document_lookup':report_document.research_report_document_lookup,
    # 本地实体库 / 用户集合
    "security_lookup": local.security_lookup,
    "industry_lookup": local.industry_lookup,
    "theme_lookup": local.theme_lookup,
    "benchmark_lookup": local.benchmark_lookup,
    "benchmark_performance_lookup": fund_index.benchmark_performance_lookup,
    "peer_group_builder": local.peer_group_builder,
    "portfolio_lookup": local.portfolio_lookup,
    "portfolio_risk_analysis": local.portfolio_risk_analysis,
    "watchlist_lookup": local.watchlist_lookup,
    # 个股 / 公司 / 事件
    "quote_history": equity.quote_history,
    "financials_lookup": equity.financials_lookup,
    "announcement_search": equity.announcement_search,
    "company_profile": equity.company_profile,
    "company_relationship_lookup": equity.company_relationship_lookup,
    "company_governance_lookup": equity.company_governance_lookup,
    "shareholder_count_lookup": equity.shareholder_count_lookup,
    "dividend_history_lookup": equity.dividend_history_lookup,
    "restricted_release_lookup": equity.restricted_release_lookup,
    "institution_survey_lookup": equity.institution_survey_lookup,
    "capital_flow_lookup": equity.capital_flow_lookup,
    "margin_balance_lookup": equity.margin_balance_lookup,
    "dragon_tiger_lookup": equity.dragon_tiger_lookup,
    "event_timeline_lookup": equity.event_timeline_lookup,
    "event_monitor_setup": service.event_monitor_setup,
    "industry_chain_lookup": service.industry_chain_lookup,
    # 基金 / 指数 / 风格 / 行业
    "fund_lookup": fund_index.fund_lookup,
    "fund_holdings_lookup": fund_index.fund_holdings_lookup,
    "fund_performance_lookup": fund_index.fund_performance_lookup,
    "index_lookup": fund_index.index_lookup,
    "index_constituents_lookup": fund_index.index_constituents_lookup,
    "index_performance_lookup": fund_index.index_performance_lookup,
    "style_performance_lookup": fund_index.style_performance_lookup,
    "style_constituents_lookup": fund_index.style_constituents_lookup,
    "industry_performance_lookup": fund_index.industry_performance_lookup,
    "theme_constituents_lookup": fund_index.theme_constituents_lookup,
    # 全市场 / 板块 / 市场情绪
    "sector_ranking_lookup": market.sector_ranking_lookup,
    "sector_fund_flow_lookup": market.sector_fund_flow_lookup,
    "market_overview_lookup": market.market_overview_lookup,
    "hot_stock_rank_lookup": market.hot_stock_rank_lookup,
    "limit_pool_lookup": market.limit_pool_lookup,
    "market_news_lookup": market.market_news_lookup,
    "etf_ranking_lookup": market.etf_ranking_lookup,
    # 业绩与估值
    "performance_forecast_lookup": valuation.performance_forecast_lookup,
    "market_valuation_lookup": valuation.market_valuation_lookup,
    "stock_valuation_lookup": valuation.stock_valuation_lookup,
    # 卖方观点 / 公告 / 海外 / 衍生品
    "research_report_lookup": coverage.research_report_lookup,
    "announcement_document_lookup": coverage.announcement_document_lookup,
    "performance_express_lookup": coverage.performance_express_lookup,
    "overseas_quote_lookup": coverage.overseas_quote_lookup,
    "forex_rate_lookup": coverage.forex_rate_lookup,
    "minute_bar_lookup": coverage.minute_bar_lookup,
    "bond_yield_curve_lookup": coverage.bond_yield_curve_lookup,
    "ipo_detail_lookup": coverage.ipo_detail_lookup,
    # 可转债
    "convertible_bond_lookup": bond.convertible_bond_lookup,
    "bond_terms_lookup": bond.bond_terms_lookup,
    # 宏观 / 大宗 / 政策
    "macro_series_lookup": macro.macro_series_lookup,
    "macro_event_search": macro.macro_event_search,
    "commodity_price_lookup": macro.commodity_price_lookup,
    "supply_demand_lookup": macro.supply_demand_lookup,
    "inventory_lookup": macro.inventory_lookup,
    "policy_search": macro.policy_search,
    "official_document_search": macro.official_document_search,
    "regional_policy_search": macro.regional_policy_search,
    # 策略自进化（只读；依赖 trading-core 在线）
    "strategy_pool_lookup": evolution.strategy_pool_lookup,
    "strategy_attribution_lookup": evolution.strategy_attribution_lookup,
    "strategy_evolution_preview": evolution.strategy_evolution_preview,
}


# 这些能力没有公开数据源，但保留处理器以便返回可审计的原因。
EXPLICIT_UNAVAILABLE = {
    "supply_demand_lookup",
}


def get_handler(tool_id: str) -> Handler | None:
    return HANDLERS.get(tool_id)


def missing_handlers() -> list[str]:
    return sorted(set(TOOL_REGISTRY) - set(HANDLERS))


def orphan_handlers() -> list[str]:
    return sorted(set(HANDLERS) - set(TOOL_REGISTRY))


def validate_toolbox() -> list[str]:
    problems: list[str] = []
    for tool_id in missing_handlers():
        problems.append(f"注册工具没有处理器: {tool_id}")
    for tool_id in orphan_handlers():
        problems.append(f"处理器没有对应的注册工具: {tool_id}")
    for tool_id, definition in TOOL_REGISTRY.items():
        handler = HANDLERS.get(tool_id)
        if definition.availability == "configured" and handler is None:
            problems.append(f"{tool_id} 标记为已配置但没有处理器")
        if (
            definition.availability == "unconfigured"
            and handler is not None
            and tool_id not in EXPLICIT_UNAVAILABLE
        ):
            problems.append(f"{tool_id} 标记为未配置却存在可执行处理器")
    return problems
