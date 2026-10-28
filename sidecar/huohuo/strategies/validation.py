"""策略输入边界；模型不提供身份、收益、验证结论或正式状态。"""
from datetime import date
from ..contracts import Invalid, text
from ..investment.service import ticker
from .legacy import genome
from ..execution import digest

RULES = {
 'ma_cross':{'fast':(5,2,30),'slow':(20,5,120)},
 'momentum':{'n':(10,2,120)}, 'breakout':{'n':(20,5,120)},
 'rsi_reversal':{'n':(14,2,60),'oversold':(30,5,45),'overbought':(70,55,95)},
 'bollinger':{'n':(20,5,120),'k':(2.,.5,4.)},
 'volume_breakout':{'n':(20,5,120),'vol_mult':(1.5,1.,5.)},
}
ACTIONS={'create','backtest','shadow','evolve','apply','retire','schedule','accept_suggestion'}
def exact(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise Invalid('请求缺少字段或包含未允许字段')
def identifier(value):
    import re
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}',value):raise Invalid('策略标识无效')
    return value

def definition(payload):
    exact(payload,('name','kind','params','securities','rationale','direction'),('source_evidence_ids',))
    name=text(payload['name'],'策略名称',100);text(payload['rationale'],'研究假设',1000)
    kind=payload['kind']
    if kind not in RULES or payload['direction'] not in ('利好','利空','其他'):raise Invalid('不支持的规则或研究方向；本版本只模拟做多')
    params=payload['params'];rules=RULES[kind]
    if not isinstance(params,dict) or set(params)-set(rules):raise Invalid('规则参数无效')
    normalized={}
    for key,(default,low,high) in rules.items():
        v=params.get(key,default)
        if type(v) not in (int,float) or not low<=v<=high or (isinstance(default,int) and int(v)!=v):raise Invalid('规则参数超出允许范围')
        normalized[key]=int(v) if isinstance(default,int) else float(v)
    if kind=='ma_cross' and normalized['fast']>=normalized['slow']:raise Invalid('快均线必须短于慢均线')
    securities=payload['securities']
    if not isinstance(securities,list) or not 1<=len(securities)<=3:raise Invalid('每项策略限 1–3 只沪深 A 股')
    for s in securities:
        exact(s,('code','name'));ticker(s['code']);text(s['name'],'证券名称',80)
    if len({s['code'] for s in securities})!=len(securities):raise Invalid('证券不能重复')
    securities=sorted(securities,key=lambda s:s['code'])
    semantic={'kind':kind,'params':normalized,'symbols':[s['code'] for s in securities],'direction':payload['direction']}
    evidence=payload.get('source_evidence_ids',[])
    if not isinstance(evidence,list) or len(evidence)>5 or len(set(evidence))!=len(evidence):raise Invalid('来源证据最多 5 条，不能重复')
    for value in evidence:text(value,'来源证据',200)
    return {'source_evidence_ids':evidence,**semantic,'id':'STR_'+digest(semantic)[:24],'name':name,'rationale':payload['rationale'],
            'securities':securities,'gene':genome.gene_for(kind,normalized,semantic['symbols'],payload['direction'])}

def validate(action,payload,today):
    if action not in ACTIONS:raise Invalid('不支持的策略操作')
    if action=='schedule':
        from .schedule import validate_policy
        return validate_policy(payload)
    if action=='accept_suggestion':
        exact(payload,('suggestion_id',));text(payload['suggestion_id'],'候选建议',100)
        return payload.copy()
    if action=='create':return definition(payload)
    if action in ('evolve','apply') and isinstance(payload,dict) and payload.get('scope')=='pool':
        exact(payload,('scope','state_version'),('preview_token',) if action=='apply' else ())
        text(payload['state_version'],'策略池版本',100)
        if action=='apply':text(payload.get('preview_token'),'预案凭证',200)
        return payload.copy()
    optional=('start_date','end_date') if action=='backtest' else ('preview_token',) if action=='apply' else ()
    exact(payload,('strategy_id','revision'),optional)
    identifier(payload['strategy_id'])
    if type(payload['revision']) is not int or payload['revision']<1:raise Invalid('策略版本无效')
    if action=='backtest':
        try:start,end=date.fromisoformat(payload['start_date']),date.fromisoformat(payload['end_date'])
        except (ValueError,TypeError,KeyError):raise Invalid('请填写有效的回测起止日期') from None
        if not 40<=(end-start).days<=1095 or end>today:raise Invalid('回测范围须为 40–1095 天，不能包含未来日期')
    if action=='apply':text(payload.get('preview_token'),'预案凭证',200)
    return payload.copy()
