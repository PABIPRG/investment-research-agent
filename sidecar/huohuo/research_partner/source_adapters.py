"""兼容旧报价／公司资料操作，不改变既有范围和来源事件身份。"""
from datetime import datetime, timezone
from ..contracts import Invalid
from ..execution import digest
_PROFILE_SOURCE = 'akshare.stock_profile_cninfo'
_PROFILE_URL = 'https://webapi.cninfo.com.cn/'
_QUOTE_SOURCE = 'eastmoney'
_QUOTE_UNITS = {'price': 'CNY/share', 'change': 'CNY', 'change_percent': '%'}

def validate_quote_document(document, binding):
    """报价同样只接受与本次范围、主体和内容指纹一致的快照。"""
    if document.get('scope') != binding:
        raise Invalid('quote evidence scope mismatch')
    raw = document.get('raw')
    if not isinstance(raw, dict):
        raise Invalid('quote evidence raw missing')
    if document.get('source_hash') != digest(raw):
        raise Invalid('quote evidence source hash mismatch')
    values = document.get('values')
    if not isinstance(values, dict):
        raise Invalid('quote evidence values missing')
    for field, unit in _QUOTE_UNITS.items():
        try:
            number = float(values[field])
        except (KeyError, TypeError, ValueError):
            raise Invalid('quote evidence values invalid') from None
        if not number == number or number in (float('inf'), float('-inf')):
            raise Invalid('quote evidence values invalid')
    if values.get('price_unit') != 'CNY/share' or values.get('currency') != 'CNY':
        raise Invalid('quote evidence unit mismatch')
    if document.get('source') != _QUOTE_SOURCE:
        raise Invalid('quote evidence source mismatch')
    from ..research import snapshot
    expected=snapshot(binding,lambda _: (raw,document.get('source_url','')))
    if document.get('method')!='quote_delta_v1' or expected.get('status')!='ok' or expected.get('values')!=values or expected.get('data_as_of')!=document.get('data_as_of'):
        raise Invalid('quote evidence semantics mismatch')
    try:
        observed = datetime.fromisoformat(document.get('observed_at', ''))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise Invalid('quote evidence observation time missing') from None

def validate_profile_document(document, binding):
    """公司资料同样只接受与本次范围、主体和内容指纹一致的来源文档。"""
    if document.get('scope') != binding:
        raise Invalid('profile evidence scope mismatch')
    raw = document.get('raw')
    if not isinstance(raw, dict) or raw.get('code') != binding['entity_id'].split(':')[-1]:
        raise Invalid('profile evidence subject mismatch')
    if document.get('source_hash') != digest(raw):
        raise Invalid('profile evidence source hash mismatch')
    rows = raw.get('records')
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise Invalid('profile evidence schema invalid')
    if document.get('values') != {'code': raw['code'], 'profile': rows[:1]}:
        raise Invalid('profile evidence semantics mismatch')
    if document.get('source') != _PROFILE_SOURCE or document.get('source_url') != _PROFILE_URL:
        raise Invalid('profile evidence source mismatch')
    try:
        observed = datetime.fromisoformat(document.get('observed_at', ''))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise Invalid('profile evidence observation time missing') from None


def quote_session(now, calendar):
    from zoneinfo import ZoneInfo
    local=datetime.fromtimestamp(now,timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'))
    minute=local.hour*60+local.minute
    if local.weekday()>=5 or not (570<=minute<690 or 780<=minute<900):return False
    return calendar.is_trading_day(local.date())
