"""旧策略只恢复为待验证候选；旧收益与执行状态独立归档。"""
from ..contracts import Invalid
from ..execution import digest
from ..strategies.validation import definition
from .facts import rows


def map_strategies(collections,existing,rule,resolver,at):
    source=collections.get('strategies',{}).get('strategies',{})
    if not isinstance(source,dict) or len(source)>100: raise Invalid('旧策略集合须为最多 100 项的对象')
    result=[];conflicts=0;skipped=0
    for old_id,record in source.items():
        if not isinstance(record,dict): raise Invalid('旧策略记录必须是对象')
        symbols=record.get('symbols')
        rows(symbols,'策略证券',3)
        securities=[]
        for symbol in symbols:
            if isinstance(symbol,str): securities.append({'code':symbol,'name':resolver(symbol) or '证券名称待补全'})
            elif isinstance(symbol,dict): securities.append({'code':symbol.get('code'),'name':symbol.get('name') or resolver(symbol.get('code')) or '证券名称待补全'})
            else: raise Invalid('旧策略证券格式无效')
        payload=definition({'name':record.get('name') or '迁入策略 '+old_id,'kind':record.get('kind'),'params':record.get('params') or {},'securities':securities,
                            'rationale':record.get('rationale') or record.get('reason') or '旧策略规则迁入；需在当前实例重新验证','direction':record.get('direction') or '其他'})
        sid='STR_'+digest({'legacy_id':old_id,'kind':payload['kind'],'params':payload['params'],'symbols':payload['symbols'],'direction':payload['direction']})[:24]
        if sid in existing:
            conflicts+=1
            if rule=='keep_local': skipped+=1;continue
        result.append({**payload,'id':sid,'revision':existing.get(sid,{}).get('revision',0)+1,'status':'candidate','verification_status':'insufficient',
            'backtest':{},'source':'legacy_import','source_refs':[],'source_evidence_ids':[],'legacy_source_id':old_id,'created_at':at,'updated_at':at,'evolve':{'state':'active','tier':1}})
    if len(set(existing)|{x['id'] for x in result})>100: raise Invalid('迁入后策略池超过 100 项')
    return result,{'incoming':len(source),'added':len(result),'conflicts':conflicts,'skipped':skipped}
