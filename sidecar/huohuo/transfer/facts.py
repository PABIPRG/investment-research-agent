"""旧持仓与成交映射为正式事实；历史成交绝不再次改变当前持仓。"""
import copy
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ..contracts import Invalid, text
from ..execution import digest
from ..investment.instruments import instrument
from ..investment.service import number


def rows(value, label, maximum=10000):
    if not isinstance(value,list) or len(value)>maximum: raise Invalid(label+'必须是有界列表')
    return value


def name_for(row, resolver):
    name=row.get('name') or resolver(row['ticker']) or '证券名称待补全'
    return text(name,'证券名称',100)


def timestamp(value, label, allow_missing=False):
    if value is None and allow_missing: return None
    if not isinstance(value,str): raise Invalid(label+'格式无效')
    try: parsed=datetime.fromisoformat(value.strip().replace(' ','T'))
    except ValueError: raise Invalid(label+'格式无效') from None
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    if parsed>datetime.now(timezone.utc): raise Invalid(label+'不能为未来时间')
    return parsed.isoformat(timespec='minutes' if re.search(r'T\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?$',value.strip().replace(' ','T')) else 'auto')


def holding(row,resolver):
    if not isinstance(row,dict): raise Invalid('持仓记录必须是对象')
    instrument(row.get('ticker'))
    quantity=number(row.get('quantity'),'数量');cost=number(row.get('cost_price'),'成本',True)
    if quantity<=0: raise Invalid('旧持仓数量须大于零')
    return {'ticker':row['ticker'],'name':name_for(row,resolver),'quantity':quantity,'cost_price':cost,
        'position_time':timestamp(row.get('position_time'),'持仓时间',True),'time_source':'legacy_import','legacy_time_source':row.get('time_source')}


def trade(row,resolver,source_id,at):
    if not isinstance(row,dict): raise Invalid('成交记录必须是对象')
    instrument(row.get('ticker'))
    side=row.get('side')
    if side not in ('buy','sell','unclassified'): raise Invalid('旧成交方向无效')
    qty=number(row.get('quantity'),'成交数量');price=number(row.get('price'),'成交价格')
    occurred=row.get('occurred',1)
    if type(occurred) is not int or occurred<1 or occurred>10000: raise Invalid('成交重复次数无效')
    if not isinstance(row.get('traded_at'),str) or 'T' not in row['traded_at'].replace(' ','T'): raise Invalid('成交时间需包含日期与时间')
    when=timestamp(row.get('traded_at'),'成交时间')
    key='legacy-trade-'+digest({'id':row.get('trade_id') or row.get('request_id'),'ticker':row['ticker'],'side':side,'price':price,'quantity':qty,'at':row.get('traded_at'),'source':row.get('source'),'account':row.get('account_mode'),'occurred':occurred})[:32]
    if side=='unclassified' or qty==0 or price==0 or row.get('account_mode')=='simulated':
        return None,key
    fees=number(row.get('fees'),'费用',True)
    payload={'request_id':key,'ticker':row['ticker'],'side':side,'quantity':qty,'price':price,'fees':fees,'traded_at':when,'affects_holdings':False}
    return {**payload,'name':name_for(row,resolver),'occurred_at':when,'recorded_at':at,'source':'legacy_import','request':payload,
        'legacy_source_id':source_id,'legacy_time_text':row.get('traded_at'),'legacy_timezone_assumed':datetime.fromisoformat(row['traded_at'].replace(' ','T')).tzinfo is None,
        'voided':bool(row.get('voided',False)),'voided_at':timestamp(row.get('voided_at'),'撤销时间',True),'revision_no':row.get('revision_no',0),
        'fees_known':fees is not None,'before_quantity':None,'after_quantity':None,'after_cost_price':None},key


def map_facts(current,collections,selected,rules,resolver,at):
    after=copy.deepcopy(current);summary={};warnings=[]
    if 'holdings' in selected:
        source=collections.get('holdings',{});document=source.get('holdings',{})
        incoming=[holding(x,resolver) for x in rows(document.get('default',[]),'持仓')]
        codes=[x['ticker'] for x in incoming]
        if len(codes)!=len(set(codes)): raise Invalid('旧持仓包含重复证券')
        existing={x['ticker']:x for x in after['default']};conflicts=0;added=0
        for item in incoming:
            old=existing.get(item['ticker'])
            if old is not None:
                if any(old.get(k)!=item.get(k) for k in ('quantity','cost_price')): conflicts+=1
                if rules['holdings']=='keep_local': continue
            if old is None: added+=1
            existing[item['ticker']]=item
        after['default']=list(existing.values())
        if 'default' in document: after['holdings_recorded']=True
        trades=[*rows(document.get('manual_trades',[]),'手工成交'),*rows(source.get('trades',{}).get('entries',[]),'成交')]
        imported={x['request_id']:x for x in after['manual_trades']};ids=set();archived=0
        for index,item in enumerate(trades):
            converted,key=trade(item,resolver,str(index),at)
            if key in ids: raise Invalid('旧成交包含重复身份和重复序号')
            ids.add(key)
            if converted is None: archived+=1;continue
            if key not in imported: imported[key]=converted
        after['manual_trades']=list(imported.values())
        if len(after['manual_trades'])>20000 or len(after['default'])>10000: raise Invalid('导入后投资记录超过上限')
        summary['holdings']={'incoming':len(incoming),'added':added,'conflicts':conflicts,'trades':len(trades)-archived,'archive_only_trades':archived}
        if archived: warnings.append(f'{archived} 笔模拟、非买卖或零数量/价格流水仅保留只读档案，不冒充实际买卖')
        if trades: warnings.append('历史成交只补记录，不重复计入持仓；未提供的费用保持未知，旧无时区成交按中国市场时间解释并保留原文字')
    if 'watchlist' in selected:
        incoming=rows(collections.get('watchlist',{}).get('watchlist',{}).get('default',[]),'自选')
        if not all(isinstance(x,str) for x in incoming) or len(set(incoming))!=len(incoming): raise Invalid('旧自选须为不重复代码列表')
        existing={x['ticker']:x for x in after['watchlist']};added=0
        for ticker in incoming:
            instrument(ticker)
            if ticker not in existing:
                existing[ticker]={'ticker':ticker,'name':resolver(ticker) or '证券名称待补全','reason':'从旧产品导入','added_at':at};added+=1
        after['watchlist']=list(existing.values());after['watchlist_recorded']=True
        summary['watchlist']={'incoming':len(incoming),'added':added,'conflicts':0}
    return after,summary,warnings
