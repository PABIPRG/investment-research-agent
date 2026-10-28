"""将用户确认的有界条件编译成正式联系策略；备注不参与执行。"""
import math
import re
from ..contracts import Invalid

METRICS = {
    'price': ('价格', 'CNY/share'), 'pct_change': ('涨跌幅', '%'),
    'change': ('涨跌额','CNY'), 'change_percent': ('涨跌幅','%'),
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
        claim=value.get('claim')
        if set(value)-{'type','claim','expected','min_confidence'} or not isinstance(claim,str) or not 1<=len(claim.strip())<=80:
            raise Invalid('语义条件需要用户明确约定的短句（最多80字）')
        if value.get('expected','met') not in {'met','unmet'}:raise Invalid('请选择有依据证实或有依据证伪时联系')
        result={'type':'semantic','claim':claim.strip(),'evidence_required':True}
        if 'expected' in value:result['expected']=value['expected']
        if 'min_confidence' in value:
            confidence=value['min_confidence']
            if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:raise Invalid('把握要求须为0至1的有限数值')
            result['min_confidence']=confidence
        return result
    if kind != 'numeric' or set(value) != {'type', 'metric', 'operator', 'threshold'}:
        raise Invalid('数值条件需要指标、比较方式和阈值')
    metric = value['metric']
    allowed = {'quote_snapshot': {'price','change','change_percent'}, 'market_quote': {'price', 'pct_change', 'volume_ratio', 'turnover', 'amount_yi'},
               'market_technical': {'rsi_14', 'macd_hist'}}.get(scope['operation'], set())
    if metric not in allowed:
        raise Invalid('当前研究范围不能提供所选指标，请先切换相应行情或技术范围')
    if value['operator'] not in {'>', '>=', '<', '<=', '==', '!='}:
        raise Invalid('比较方式无效')
    threshold = value['threshold']
    if type(threshold) not in (int, float) or not math.isfinite(threshold):
        raise Invalid('阈值必须是有限数值')
    return dict(value, unit=METRICS[metric][1], method_version='quote_snapshot_v1' if scope['operation']=='quote_snapshot' else 'market_v1',
                basis_ref='用户明确约定' if scope['operation']=='quote_snapshot' else 'user_confirmed_contact_rule')


def readable_rule(rule):
    """供详情直接读；原始条件仍在正式 revision 中可审计。"""
    if not rule:
        return '有证据的重要变化时联系'
    names = {'condition': '条件满足时联系', 'scheduled_delivery': '按时交付研究结果',
             'periodic_check': '定时检查，条件满足才联系', 'due_reminder': '到时直接提醒'}
    def describe(c):
        if c.get('type') in {'all','any'}:
            return '（'+(' 且 ' if c['type']=='all' else ' 或 ').join(describe(x) for x in c['conditions'])+'）'
        if c.get('type')=='semantic':
            claim='出现有依据的重要变化' if c.get('claim')=='notable_change' else str(c.get('claim') or '条件缺失')
            return '有依据证伪：'+claim if c.get('expected')=='unmet' else claim
        return f"{METRICS[c['metric']][0]} {c['operator']} {c['threshold']} {METRICS[c['metric']][1]}"
    condition = ' · '+describe(rule['condition']) if rule.get('condition') else ''
    return names.get(rule.get('mode'), '联系规则') + condition + (f" · 每日 {rule['time']}（北京时间）" if rule.get('time') else '')


def normalize_contact_input(body):
    """旧 API 仅在入口适配；规则仍由同一编译器验证，原请求指纹另行保留。"""
    if 'contact_condition' not in body:return body
    if 'contact_rule' in body:raise Invalid('联系规则与旧条件不能同时提供')
    value=body['contact_condition']
    if value is None:value={'type':'semantic','claim':'notable_change'}
    if not isinstance(value,dict):raise Invalid('联系条件须为对象')
    condition={'type':'semantic',**value}
    unit=condition.pop('unit',None)
    if unit is not None and (condition.get('metric') not in METRICS or unit!=METRICS[condition['metric']][1]):raise Invalid('条件单位与指标不一致')
    compatible={k:v for k,v in body.items() if k!='contact_condition'}
    if compatible.get('reminder_time','absent') is None:compatible.pop('reminder_time')
    return {**compatible,'contact_rule':{'mode':'condition','condition':condition}}


def policy_rule(policy):
    """只读展示旧记录；不改写旧 revision 或重新授权。"""
    def condition(value):
        if not isinstance(value,dict):return None
        if value.get('type') in {'all','any'}:return {'type':value['type'],'conditions':[condition(c) for c in value.get('conditions',[])]}
        return {k:v for k,v in value.items() if k in {'type','claim','expected','min_confidence','metric','operator','threshold'}}
    return {'mode':policy.get('mode','condition'),'condition':condition(policy.get('condition'))}
