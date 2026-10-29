"""投资事实中的持仓风险约定；激活成本由核心绑定持有，不静默漂移。"""
import copy
import math
from datetime import datetime,timezone
from ..contracts import Invalid
from ..investment.instruments import instrument,identity
from .legacy import TARGET_KINDS,_parse_time,_time_status,_resolved_price

def exact(body,keys):
    if not isinstance(body,dict) or set(body)!=set(keys):raise Invalid('持仓风险设置字段无效')
def document(facts):return copy.deepcopy(facts.get('position_risk',{'global':None,'overrides':{},'rearms':{}}))
def selected(settings,code):
    return ('override',settings['overrides'][code]) if code in settings['overrides'] else ('global',settings['global'])
def status(config,at=None):
    if not config:return 'unconfigured'
    if config['monitoring_disabled']:return 'disabled'
    return _time_status(config,at)
def scope(code):
    from ..contracts import scope as validate
    eid=identity(code)
    exchange='SSE' if code.startswith(('600','601','603','605','688','689','5')) else 'SZSE'
    return validate({'entity_id':eid,'exchange':exchange,'operation':'quote_snapshot' if eid.startswith('FUND:') else 'market_quote'})
def target(value,kind,global_config):
    exact(value,('enabled','mode','value'))
    enabled,mode,amount=value['enabled'],value['mode'],value['value']
    if type(enabled) is not bool or mode not in ('percent','price') or (global_config and mode!='percent'):raise Invalid('全局目标使用百分比，单仓可用百分比或绝对价格')
    if not enabled:return {'enabled':False,'mode':mode,'value':None}
    if type(amount) not in (int,float) or not math.isfinite(amount) or not 0<amount<=1e12:raise Invalid('启用目标须为有限正数')
    if kind=='stop_loss' and mode=='percent' and amount>=1:raise Invalid('止损百分比须小于100%')
    return dict(value)
def normalize(raw,previous,global_config):
    exact(raw,('take_profit','stop_loss','effective_at','expires_at','monitoring_disabled'))
    if type(raw['monitoring_disabled']) is not bool:raise Invalid('停用标记必须明确选择')
    result={kind:target(raw[kind],kind,global_config) for kind in TARGET_KINDS}
    result.update(version=(previous or {}).get('version',0)+1,monitoring_disabled=raw['monitoring_disabled'])
    for field in ('effective_at','expires_at'):
        at=_parse_time(raw[field]);result[field]=at.isoformat() if at else None
    _time_status(result)
    return result
def apply(facts,payload):
    if not isinstance(payload,dict):raise Invalid('持仓风险操作无效')
    operation=payload.get('operation');settings=document(facts)
    holdings={x['ticker']:x for x in facts['default'] if x['quantity']>0}
    if operation=='global':
        exact(payload,('operation','config'))
        settings['global']=normalize(payload['config'],settings['global'],True)
        affected=[code for code in holdings if code not in settings['overrides']]
    elif operation=='override':
        exact(payload,('operation','ticker','config'));code=payload['ticker'];instrument(code)
        if code not in holdings:raise Invalid('只能为当前持仓设置单仓覆盖')
        settings['overrides'][code]=normalize(payload['config'],settings['overrides'].get(code),False);affected=[code]
    elif operation=='remove_override':
        exact(payload,('operation','ticker'));code=payload['ticker'];instrument(code)
        settings['overrides'].pop(code,None);affected=[code] if code in holdings else []
    elif operation=='rearm':
        exact(payload,('operation','ticker','kind'));code=payload['ticker'];kind=payload['kind'];instrument(code)
        if kind not in TARGET_KINDS or code not in holdings:raise Invalid('只能重新布防当前持仓的有效目标')
        _,config=selected(settings,code)
        if status(config)!='active' or not config[kind]['enabled']:raise Invalid('当前配置不能重新布防')
        if holdings[code]['cost_price'] is None or holdings[code]['cost_price']<=0:raise Invalid('当前成本未知或非正，不能重新布防')
        key=code+':'+kind;settings['rearms'][key]=settings['rearms'].get(key,0)+1;affected=[code]
    else:raise Invalid('持仓风险操作无效')
    proposals=[]
    for code in affected:
        source,config=selected(settings,code);state=status(config)
        holding=holdings[code];cost=holding['cost_price'];targets={}
        if state in ('active','scheduled'):
            if cost is None or cost<=0:state='cost_unknown'
            else:
                scope(code)
                for kind in TARGET_KINDS:
                    if operation=='rearm' and kind!=payload['kind']:continue
                    if config[kind]['enabled']:targets[kind]={'basis_cost':cost,'resolved_price':_resolved_price(kind,config[kind],cost)}
        proposals.append({'ticker':code,'source':source,'status':state,'targets':targets})
    return settings,{'operation':operation,'plans':proposals,'future_holdings':operation=='global',
        'notice':'确认后建立或替换对应价格联系委托，仅应用内提醒；全局配置也适用于后续明确录入的持仓。成本按激活时快照冻结，变化后需明确重新布防，不下单。'}
