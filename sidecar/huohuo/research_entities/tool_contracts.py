"""DSH 工具参数的唯一事实源。新增工具必须显式补全契约，生成器禁止猜参数。"""
import ast
from pathlib import Path
from types import SimpleNamespace


def _definitions():
    # 只读取注册表中的静态 _tool 调用，不执行处理器或加载运行依赖。
    tree = ast.parse(Path(__file__).with_name('registry').joinpath('tools.py').read_text())
    definitions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_tool':
            values = [ast.literal_eval(a) for a in node.args]
            key, name, category, availability, implementation, description = values[:6]
            if key in definitions: raise ValueError('重复工具 ID: '+key)
            keywords = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
            definitions[key] = SimpleNamespace(name=name,description=description,category=category,availability=availability,
                requires_authorization=keywords.get('requires_authorization', values[6] if len(values)>6 else False))
    return definitions

TOOL_REGISTRY = _definitions()

TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 200}
FIELDS = {
    'code': {**TEXT, 'description': '公开数据源代码；查询候选用，不表示已确认对象'},
    'name': {**TEXT, 'description': '名称或检索词'},
    'keyword': {**TEXT, 'description': '公开资料检索关键词'},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 1095},
    'periods': {'type': 'integer', 'minimum': 1, 'maximum': 20},
    'start_date': {'type': 'string', 'pattern': '^\\d{4}-\\d{2}-\\d{2}$'},
    'end_date': {'type': 'string', 'pattern': '^\\d{4}-\\d{2}-\\d{2}$'},
    'adjust': {'type': 'string', 'enum': ['qfq', 'hfq']},
    'include_members': {'type': 'boolean'},
    'member_limit': {'type': 'integer', 'minimum': 1, 'maximum': 500},
    'year': {'type': 'string', 'pattern': '^20\\d{2}$'},
    'pages': {'type': 'integer', 'minimum': 1, 'maximum': 5},
    'page': {'type': 'integer', 'minimum': 1, 'maximum': 10},
    'doc_type': {'type': 'string', 'enum': ['国务院文件', '部门文件']},
    'sort': {'type': 'string', 'enum': ['date', 'score']},
    'strategy_id': TEXT,
    'depth_up': {'type': 'integer', 'minimum': 0, 'maximum': 3},
    'depth_down': {'type': 'integer', 'minimum': 0, 'maximum': 3},
    'top_up': {'type': 'integer', 'minimum': 1, 'maximum': 20},
    'top_down': {'type': 'integer', 'minimum': 1, 'maximum': 20},
    'sector_type': {'type': 'string', 'enum': ['行业', '概念']},
    'sector_sort': {'type': 'string', 'enum': ['涨幅', '跌幅', '净流入', '上涨家数', '成交额']},
    'flow_type': {'type': 'string', 'enum': ['行业资金流', '概念资金流', '地域资金流']},
    'indicator': {'type': 'string', 'enum': ['今日', '5日', '10日']},
    'rank_type': {'type': 'string', 'enum': ['人气榜', '飙升榜']},
    'pool_type': {'type': 'string', 'enum': ['涨停', '跌停', '强势', '炸板']},
    'news_source': {'type': 'string', 'enum': ['全部', '财联社', '东方财富']},
    'etf_sort': {'type': 'string', 'enum': ['涨幅', '跌幅', '成交额', '成交量']},
    'report_period': {'type': 'string', 'pattern': '^20\\d{2}(0331|0630|0930|1231)$',
                      'description': '报告期，形如 20260930'},
    'forecast_type': {'type': 'string',
                      'enum': ['全部', '预增', '预减', '扭亏', '首亏', '续盈', '续亏', '略增', '略减', '不确定']},
    'index_name': {'type': 'string', 'enum': ['全A', '沪深300', '上证50', '中证500', '中证1000', '中证800']},
    'valuation_indicator': {'type': 'string', 'enum': ['总市值', '市盈率(TTM)', '市盈率(静)', '市净率', '市现率']},
    'valuation_period': {'type': 'string', 'enum': ['近一年', '近三年', '近五年', '近十年', '全部']},
    'market': {'type': 'string', 'enum': ['港股', '美股']},
    'minute_period': {'type': 'string', 'enum': ['1', '5', '15', '30', '60']},
}
WINDOW = 'start_date end_date days limit'
# 对象工具不开放 code/name 覆盖：实体由本会话确认回执绑定。
PARAMS = {
    'security_lookup': 'code name', 'industry_lookup': 'include_members member_limit',
    'theme_lookup': '', 'benchmark_lookup': '', 'benchmark_performance_lookup': WINDOW,
    'peer_group_builder': 'limit', 'portfolio_lookup': '', 'portfolio_risk_analysis': '', 'watchlist_lookup': '',
    'quote_history': WINDOW+' adjust', 'financials_lookup': 'periods', 'announcement_search': WINDOW,
    'company_profile': '', 'company_relationship_lookup': '', 'company_governance_lookup': '',
    'shareholder_count_lookup': 'limit', 'dividend_history_lookup': 'limit',
    'restricted_release_lookup': WINDOW, 'institution_survey_lookup': 'days limit',
    'capital_flow_lookup': '', 'margin_balance_lookup': 'days', 'dragon_tiger_lookup': WINDOW,
    'event_timeline_lookup': 'days limit', 'event_monitor_setup': '',
    'industry_chain_lookup': 'depth_up depth_down top_up top_down',
    'fund_lookup': 'code name limit', 'fund_holdings_lookup': 'year limit', 'fund_performance_lookup': WINDOW,
    'index_lookup': 'code name', 'index_constituents_lookup': 'limit', 'index_performance_lookup': WINDOW,
    'style_performance_lookup': WINDOW, 'style_constituents_lookup': 'limit',
    'industry_performance_lookup': WINDOW, 'theme_constituents_lookup': 'pages limit',
    'convertible_bond_lookup': 'code name', 'bond_terms_lookup': '',
    'macro_series_lookup': 'limit', 'macro_event_search': 'keyword days limit',
    'commodity_price_lookup': WINDOW, 'supply_demand_lookup': '', 'inventory_lookup': 'limit',
    'policy_search': 'keyword days limit', 'official_document_search': 'keyword doc_type page limit sort',
    'regional_policy_search': 'keyword days limit',
    'sector_ranking_lookup': 'sector_type sector_sort limit',
    'sector_fund_flow_lookup': 'flow_type indicator limit',
    'market_overview_lookup': '',
    'hot_stock_rank_lookup': 'rank_type limit',
    'limit_pool_lookup': 'pool_type days limit',
    'market_news_lookup': 'keyword news_source limit',
    'etf_ranking_lookup': 'keyword etf_sort limit',
    'performance_forecast_lookup': 'report_period forecast_type keyword limit',
    'market_valuation_lookup': 'index_name limit',
    'stock_valuation_lookup': 'valuation_indicator valuation_period limit',
    'research_report_lookup': 'limit',
    'announcement_document_lookup': 'days keyword limit',
    'performance_express_lookup': 'report_period keyword limit',
    'overseas_quote_lookup': 'market code days limit',
    'forex_rate_lookup': 'keyword limit',
    'minute_bar_lookup': 'minute_period limit',
    'bond_yield_curve_lookup': 'days limit',
    'ipo_detail_lookup': 'limit',
    'strategy_pool_lookup': 'strategy_id', 'strategy_attribution_lookup': 'strategy_id', 'strategy_evolution_preview': 'strategy_id',
}
DISCOVERY = {'security_lookup', 'fund_lookup', 'index_lookup', 'convertible_bond_lookup'}
GLOBAL = {'macro_event_search', 'policy_search', 'official_document_search', 'regional_policy_search',
          'portfolio_lookup', 'portfolio_risk_analysis', 'watchlist_lookup', 'event_monitor_setup',
          'strategy_pool_lookup', 'strategy_attribution_lookup', 'strategy_evolution_preview',
          'sector_ranking_lookup', 'sector_fund_flow_lookup', 'market_overview_lookup',
          'hot_stock_rank_lookup', 'limit_pool_lookup', 'market_news_lookup', 'etf_ranking_lookup',
          'performance_forecast_lookup', 'market_valuation_lookup',
          'performance_express_lookup',
          'overseas_quote_lookup', 'forex_rate_lookup', 'bond_yield_curve_lookup'}

def catalog():
    if set(PARAMS) != set(TOOL_REGISTRY):
        raise ValueError('工具与参数契约不一致，必须补全契约再生成')
    result = []
    for key, tool in sorted(TOOL_REGISTRY.items()):
        props = {k: FIELDS[k] for k in PARAMS[key].split()}
        required = []
        if key not in DISCOVERY | GLOBAL:
            props['confirmation_id'] = {**TEXT, 'description': '当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执'}
            required.append('confirmation_id')
        if key in {'macro_event_search','policy_search','official_document_search','regional_policy_search'}:
            required.append('keyword')
        description = f'{tool.name}：{tool.description} 返回真实状态、来源、时间及证据编号。'
        if tool.requires_authorization or key=='event_monitor_setup':
            description += '当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。'
        result.append({'name': key, 'title': tool.name, 'category': tool.category,
                       'requires_authorization': tool.requires_authorization or key=='event_monitor_setup',
                       'description': description, 'availability': tool.availability,
                       'parameters': {'type':'object','properties':props,'required':required,'additionalProperties':False}})
    return result

def validate_args(tool_id, args):
    import re
    from datetime import date
    from ..contracts import Invalid
    entry = next((t for t in catalog() if t['name']==tool_id), None)
    if entry is None or not isinstance(args,dict): raise Invalid('未知工具或参数格式错误')
    schema=entry['parameters']; properties=schema['properties']
    if set(args)-set(properties) or set(schema['required'])-set(args): raise Invalid('参数缺失或包含未允许字段')
    for k,v in args.items():
        s=properties[k]; kind=s['type']
        if kind=='string':
            if not isinstance(v,str) or not s.get('minLength',1)<=len(v)<=s.get('maxLength',200): raise Invalid('文本参数无效：'+k)
            if s.get('pattern') and not re.fullmatch(s['pattern'],v):raise Invalid('格式错误：'+k)
        elif kind=='integer':
            if type(v) is not int or not s['minimum']<=v<=s['maximum']:raise Invalid('整数参数越界：'+k)
        elif kind=='boolean' and type(v) is not bool:raise Invalid('布尔参数无效：'+k)
        if 'enum' in s and v not in s['enum']:raise Invalid('枚举值无效：'+k)
        if k in ('start_date','end_date'):
            try:date.fromisoformat(v)
            except ValueError:raise Invalid('日期无效：'+k) from None
    if tool_id in DISCOVERY and not (args.get('code') or args.get('name')):raise Invalid('请提供代码或名称以查询候选')
    if args.get('start_date','') > args.get('end_date','9999-12-31'):raise Invalid('起始日期晚于截止日期')
    return dict(args)
