"""历史资料可以留存，但只有仍满足当前口径的资料才获得联系资格。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from ..market.contracts import UNITS
from ..market.brief_basis import validate_brief_basis


def fresh_for_contact(document, scope, now, calendar=None):
    raw, data = document.get('raw', {}), document.get('values', {})
    operation = scope['operation']
    at = datetime.fromtimestamp(now, timezone.utc)
    def age(stamp, seconds):
        try:
            parsed = datetime.fromisoformat(stamp)
            return parsed.tzinfo is not None and -60 <= now-parsed.timestamp() <= seconds
        except (ValueError, TypeError): return False
    if operation=='quote_snapshot':
        return age(document.get('data_as_of'),900) and age(document.get('observed_at'),900) and data.get('currency')=='CNY' and data.get('price_unit')=='CNY/share'
    if operation == 'market_brief':
        return age(document.get('observed_at'),300) and calendar is not None and validate_brief_basis(raw, scope['period'], calendar, now=at)['status']=='ok'
    if raw.get('complete') is not True or raw.get('stale') is not False or raw.get('cache')=='stale': return False
    if operation == 'market_quote':
        rows = data.get('items', [])
        return len(rows)==1 and rows[0].get('time_known') is True and age(rows[0].get('as_of'),180) and all(rows[0].get('units',{}).get(k)==v for k,v in UNITS.items() if k in ('price','pct_change','volume_ratio','turnover','amount_yi'))
    if operation == 'market_technical':
        try:
            through = datetime.strptime(data['through'], '%Y-%m-%d').date()
            distance = (at.astimezone(ZoneInfo('Asia/Shanghai')).date()-through).days
            return 0<=distance<=4 and data.get('adjustment')=='qfq' and data.get('units',{}).get('close')=='CNY/share' and age(document.get('observed_at'),300)
        except (ValueError, TypeError, KeyError):return False
    if operation == 'news':
        return raw.get('status') in ('ok','empty') and age(document.get('observed_at'),300)
    return False


def evidence_is_current(db, attempt_id, result, scope, now, calendar=None):
    import json
    ids=result.get('evidence_ids',[])
    if not ids:return False
    for ref in ids:
        row=db.execute('SELECT document FROM evidence WHERE id=? AND attempt_id=?',(ref,attempt_id)).fetchone()
        if not row or not fresh_for_contact(json.loads(row[0]),scope,now,calendar):return False
    return True
