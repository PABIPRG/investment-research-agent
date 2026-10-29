"""当前主体投资事实的账户读模型；只查询公开代码，不持久化第二套账户。"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from ..market.contracts import number, source_time

CN=ZoneInfo('Asia/Shanghai')

def decimal(value):
    n=number(value)
    return Decimal(str(value)) if n is not None and not isinstance(value,bool) else None

def metric(value=None,status='unavailable',reason=''):
    return {'value':float(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if value is not None else None,
            'status':status,'reason':reason,'currency':'CNY'}

def dated(value):
    stamp=source_time(value)
    return datetime.fromisoformat(stamp).astimezone(CN) if stamp else None

def account_view(facts,market,*,now=None):
    now=now or datetime.now(timezone.utc)
    today=now.astimezone(CN).date()
    positions={p['ticker']:p for p in facts['holdings']}
    current={c:decimal(p['quantity']) for c,p in positions.items()}
    active=[t for t in facts['trades'] if not t.get('voided')]
    trades=[t for t in active if dated(t.get('traded_at')) and dated(t['traded_at']).date()==today]
    daily_reason=''
    if any(not dated(t.get('traded_at')) for t in active):daily_reason='成交时间缺失，无法核对当日基准'
    if any(not t.get('affects_holdings',True) for t in trades):daily_reason='当日有仅补记录的成交，持仓基准待核对'
    trades=[t for t in trades if t.get('affects_holdings',True)]
    net={};cash=Decimal(0)
    for t in trades:
        signed=decimal(t['quantity'])*(1 if t['side']=='buy' else -1)
        net[t['ticker']]=net.get(t['ticker'],Decimal(0))+signed
        cash+=signed*decimal(t['price'])+decimal(t.get('fees',0))
    opening={c:current.get(c,Decimal(0))-net.get(c,Decimal(0)) for c in current.keys()|net.keys()}
    if any(q<0 for q in opening.values()):daily_reason='当日成交与当前持仓无法对齐，昨收持仓基准待核对'
    for c,p in positions.items():
        stamp=dated(p.get('position_time'))
        if c not in net and (not stamp or stamp.date()>=today):daily_reason='持仓确认时点不足以确定昨收数量'
    for c in facts.get('corrections',[]):
        stamp=dated(c.get('effective_at'))
        before=(c.get('before') or {}).get('quantity',0);after=(c.get('after') or {}).get('quantity',0)
        if before!=after and (not stamp or stamp.date()>=today):daily_reason='当日手工校正过持仓数量，昨收基准待核对'
    needed=sorted(c for c in opening.keys()|current.keys() if current.get(c,0)>0 or opening.get(c,0)>0)
    quotes={};warnings=[];sources=[]
    if len(needed)>20:
        warnings.append('本次账户行情最多覆盖20只证券，当前持仓超出边界，未展示部分合计')
    elif needed:
        try:
            result=market.query({'operation':'quotes','codes':needed,'asset_scope':'investment'})
            warnings.extend(result.get('warnings',[]))
            rows=result.get('data',{}).get('items',[]) if result.get('status')=='ok' else []
            counts=Counter(r.get('code') for r in rows)
            for row in rows:
                code=row.get('code');stamp=dated(row.get('as_of'));price=decimal(row.get('price'))
                if code not in needed or counts[code]!=1 or not stamp or not price or price<=0 or row.get('units',{}).get('price')!='CNY/share':continue
                if (stamp-now.astimezone(CN)).total_seconds()>30:continue
                row=dict(row,stale=bool(result.get('stale') or row.get('stale') or (now.astimezone(CN)-stamp).total_seconds()>180))
                quotes[code]=row
                sources.append({'code':code,'source':row.get('source') or result.get('source'),'as_of':row.get('as_of'),'stale':row['stale']})
        except Exception:
            warnings.append('行情读取失败，请重试；不表示市值为零')
    missing=[c for c in needed if c not in quotes]
    market_value=Decimal(0)
    for code,q in current.items():
        if code not in quotes:market_value=None;break
        market_value+=q*decimal(quotes[code]['price'])
    stale=any(quotes[c]['stale'] for c in current if c in quotes)
    mv=metric(market_value,'stale' if stale else 'ok', '旧行情参考，非实时市值' if stale else '按本地持仓数量与来源报价计算') if market_value is not None else metric(reason='持仓行情未完整返回，请重试；未将缺失报价计为零')
    costs=[decimal(p.get('cost_price')) for p in positions.values()]
    cost=metric(sum((current[c]*decimal(p['cost_price']) for c,p in positions.items()),Decimal(0)),'ok','本地已记录持仓成本，不含现金') if all(c is not None for c in costs) else metric(reason='持仓成本待补全')
    pnl=-cash
    for code,quantity in opening.items():
        row=quotes.get(code)
        if current.get(code,0)==0 and quantity==0:continue
        if not row or dated(row.get('as_of')).date()!=today:
            daily_reason=daily_reason or '当日行情尚未完整返回，不能用上一交易日报价代替';break
        latest_trade=max((dated(t['traded_at']) for t in trades if t['ticker']==code),default=None)
        if latest_trade and dated(row['as_of'])<latest_trade:
            daily_reason=daily_reason or '报价早于当日成交，等待更新行情';break
        previous=decimal(row.get('previous_close'))
        if quantity>0 and (previous is None or previous<=0 or row.get('units',{}).get('previous_close')!='CNY/share'):
            daily_reason=daily_reason or '昨收价格缺失或单位未核验';break
        pnl+=current.get(code,Decimal(0))*decimal(row['price'])-quantity*(previous or Decimal(0))
    daily=metric(reason=daily_reason) if daily_reason else metric(pnl,'stale' if any(r['stale'] for r in quotes.values()) else 'ok','按昨收数量、当前报价、当日已记录成交与费用计算；不含未录入分红税费')
    return {'fact_version':facts['version'],'observed_at':now.isoformat(),'holdings_status':facts['holdings_status'],
            'holdings_count':len(positions),'watchlist_count':len(facts['watchlist']),
            'market_value':mv,'holding_cost':cost,'daily_pnl':daily,'sources':sources,'missing_codes':missing,
            'warnings':warnings,'scope_note':'仅统计本地投资记录，不是券商账户余额；未录入不代表券商空仓。'}
