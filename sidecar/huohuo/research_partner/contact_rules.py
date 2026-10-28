"""将用户确认的有界条件编译成正式联系策略；备注不参与执行。"""
import math
import re
from ..contracts import Invalid

METRICS = {
    'price': ('价格', 'CNY/share'), 'pct_change': ('涨跌幅', '%'),
    'volume_ratio': ('量比', 'ratio'), 'turnover': ('换手率', '%'),
    'amount_yi': ('成交额', 'CNY/100000000'),
    'rsi_14': ('RSI(14)', 'index'), 'macd_hist': ('MACD 柱', 'CNY/share'),
}
OPERATIONS = {'condition', 'scheduled_delivery', 'periodic_check', 'due_reminder'}


def compile_rule(rule, scope, channels):
    if not isinstance(rule, dict) or set(rule) - {
        'mode', 'condition', 'time', 'trading_days_only', 'notify_on', 'cooldown_minutes'
    }:
        raise Invalid('联系规则字段无效')
    mode = rule.get('mode')
    if mode not in OPERATIONS:
        raise Invalid('请选择条件联系、定时交付、周期检查或到期提醒')
    policy = {'mode': mode, 'channels': channels, 'max_retries': 0}
    notify = rule.get('notify_on', 'transition')
    if notify not in {'transition', 'first_entry', 'reentry', 'level'}:
        raise Invalid('提醒时机无效')
    minutes = rule.get('cooldown_minutes', 60)
    if type(minutes) is not int or not 0 <= minutes <= 43200:
        raise Invalid('提醒间隔须为 0 至 43200 分钟')
    policy.update(notify_on=notify, cooldown_seconds=minutes * 60)
    if mode in {'condition', 'periodic_check'}:
        policy['condition'] = compile_condition(rule.get('condition'), scope)
    elif rule.get('condition') is not None:
        raise Invalid('定时交付和到期提醒不接受条件；条件检查请选择周期检查')
    if mode != 'condition':
        clock = rule.get('time')
        if not isinstance(clock, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', clock):
            raise Invalid('每日时间须为 HH:MM')
        trading = rule.get('trading_days_only', False)
        if type(trading) is not bool:
            raise Invalid('交易日选项无效')
        hour, minute = map(int, clock.split(':'))
        policy['schedule'] = {'cron': f'{minute} {hour} * * *', 'timezone': 'Asia/Shanghai',
                              'catchup_seconds': 3600, 'trading_days_only': trading}
        if mode == 'due_reminder':
            policy['reminder_time'] = clock
    elif 'time' in rule or 'trading_days_only' in rule:
        raise Invalid('条件联系不需要每日时间')
    return policy


def compile_condition(value, scope, depth=0, budget=None):
    budget = budget if budget is not None else [24]
    budget[0] -= 1
    if depth > 4 or budget[0] < 0 or not isinstance(value, dict):
        raise Invalid('条件过于复杂或缺少条件')
    kind = value.get('type')
    if kind in {'all', 'any'}:
        children = value.get('conditions')
        if set(value) != {'type', 'conditions'} or not isinstance(children, list) or not 1 <= len(children) <= 8:
            raise Invalid('组合条件需要 1 至 8 项')
        return {'type': kind, 'conditions': [compile_condition(c, scope, depth + 1, budget) for c in children]}
    if kind == 'semantic':
        if set(value) != {'type', 'claim'} or value.get('claim') != 'notable_change':
            raise Invalid('语义条件仅支持有证据的重要变化')
        return {'type': 'semantic', 'claim': 'notable_change', 'evidence_required': True}
    if kind != 'numeric' or set(value) != {'type', 'metric', 'operator', 'threshold'}:
        raise Invalid('数值条件需要指标、比较方式和阈值')
    metric = value['metric']
    allowed = {'market_quote': {'price', 'pct_change', 'volume_ratio', 'turnover', 'amount_yi'},
               'market_technical': {'rsi_14', 'macd_hist'}}.get(scope['operation'], set())
    if metric not in allowed:
        raise Invalid('当前研究范围不能提供所选指标，请先切换相应行情或技术范围')
    if value['operator'] not in {'>', '>=', '<', '<=', '==', '!='}:
        raise Invalid('比较方式无效')
    threshold = value['threshold']
    if type(threshold) not in (int, float) or not math.isfinite(threshold):
        raise Invalid('阈值必须是有限数值')
    return dict(value, unit=METRICS[metric][1], method_version='market_v1',
                basis_ref='user_confirmed_contact_rule')


def readable_rule(rule):
    """供详情直接读；原始条件仍在正式 revision 中可审计。"""
    if not rule:
        return '有证据的重要变化时联系'
    names = {'condition': '条件满足时联系', 'scheduled_delivery': '按时交付研究结果',
             'periodic_check': '定时检查，条件满足才联系', 'due_reminder': '到时直接提醒'}
    def describe(c):
        if c.get('type') in {'all','any'}:
            return '（'+(' 且 ' if c['type']=='all' else ' 或 ').join(describe(x) for x in c['conditions'])+'）'
        if c.get('type')=='semantic': return '出现有依据的重要变化'
        return f"{METRICS[c['metric']][0]} {c['operator']} {c['threshold']} {METRICS[c['metric']][1]}"
    condition = ' · '+describe(rule['condition']) if rule.get('condition') else ''
    return names.get(rule.get('mode'), '联系规则') + condition + (f" · 每日 {rule['time']}（北京时间）" if rule.get('time') else '')
