"""行情能力到研究证据的唯一适配；数值条件仅消费来源值。"""
import math
from datetime import datetime, timezone
from ..contracts import Invalid, scope as validate_scope
from ..execution import digest
from .contact_rules import METRICS

MARKET_OPERATIONS = {'market_quote', 'market_technical', 'news', 'market_brief'}
HOOKS = {'market_quote': 'market.quote_changed', 'market_technical': 'market.technical_changed',
         'news': 'market.news_changed', 'market_brief': 'market.brief_changed'}


def collect_market(scope, market, calendar=None):
    sc = validate_scope(scope)
    code, operation = sc['entity_id'].split(':')[-1], sc['operation']
    requests = {
        'market_quote': {'operation': 'quotes', 'codes': [code]},
        'market_technical': {'operation': 'technical', 'code': code, 'lookback': 120},
        'news': {'operation': 'news', 'code': code, 'limit': 20},
        'market_brief': {'operation': 'brief', 'codes': [code], 'period': sc.get('period')},
    }
    if operation not in requests:
        raise Invalid('不支持的市场资料范围')
    response = market.query(requests[operation])
    now = datetime.now(timezone.utc).isoformat()
    base = {'schema_version': 1, 'scope': sc, 'observed_at': now, 'method': 'market_v1',
            'source': 'market:' + operation, 'data_as_of': response.get('as_of'),
            'limitations': response.get('warnings', []), 'values': response.get('data', {}),
            'raw': response, 'source_hash': digest(response)}
    if operation == 'market_brief':
        from ..market.brief_basis import validate_brief_basis
        if calendar is None:
            return dict(base, status='unavailable', reason='calendar_unavailable')
        basis = validate_brief_basis(response, sc['period'], calendar)
        if basis['status'] != 'ok':
            return dict(base, status='unavailable', reason=basis['reason'], basis=basis)
        base.update(basis=basis, data_as_of=basis['as_of'])
    empty_news = operation == 'news' and response.get('status') == 'empty'
    if response.get('status') != 'ok' and not empty_news:
        return dict(base, status=response.get('status', 'unavailable'), reason='market_source_unavailable')
    if operation != 'market_brief' and (response.get('stale') is not False or response.get('complete') is not True):
        return dict(base, status='unavailable', reason='market_source_stale_or_partial')
    if operation == 'market_quote':
        rows = response.get('data', {}).get('items', [])
        if len(rows) != 1 or rows[0].get('code') != code or not rows[0].get('time_known'):
            return dict(base, status='unavailable', reason='market_quote_time_or_subject_unknown')
    document = dict(base, status='ok')
    validate_market_document(document, sc)
    return document


def validate_market_document(document, scope):
    if document.get('scope') != scope or document.get('method') != 'market_v1':
        raise Invalid('行情资料范围或方法不匹配')
    raw = document.get('raw')
    if not isinstance(raw, dict) or document.get('source_hash') != digest(raw):
        raise Invalid('行情资料指纹不匹配')
    is_brief = scope['operation'] == 'market_brief'
    allowed = {'ok','empty'} if scope['operation']=='news' else {'ok'}
    if raw.get('status') not in allowed or raw.get('complete') is not True or (not is_brief and raw.get('stale') is not False):
        raise Invalid('缺失或过时行情不能作为新的判断依据')
    if is_brief:
        basis = document.get('basis', {})
        if basis.get('status') != 'ok' or basis.get('basis') != 'closing_reference' or basis.get('period') != scope['period'] or not basis.get('reference_date') or basis.get('as_of') != document.get('data_as_of'):
            raise Invalid('简报缺少程序核验的收盘口径')
    if document.get('values') != raw.get('data'):
        raise Invalid('行情来源值不一致')
    data = raw.get('data', {})
    code = scope['entity_id'].split(':')[-1]
    if scope['operation'] == 'market_quote':
        rows = data.get('items')
        if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('code') != code or not rows[0].get('time_known'):
            raise Invalid('行情来源证券或时间无法核对')
    if scope['operation'] == 'market_technical' and data.get('code') != code:
        raise Invalid('技术指标来源证券不匹配')


def content_version(document):
    # observed_at 和缓存命中不是资料变化，不能因轮询本身触发研究。
    def stable(value):
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items() if k not in {
                'observed_at', 'as_of', 'cache_hit', 'cached', 'fetched_at', 'warnings', 'stale', 'complete'}}
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value
    return digest(stable(document['values']))


def bound_metrics(db, attempt_id, result, scope):
    """从已入库证据取数，覆盖模型自报 metrics；缺字段保持未知。"""
    import json
    output, candidates = {}, []
    for ref in result.get('evidence_ids', []):
        row = db.execute('SELECT document FROM evidence WHERE id=? AND attempt_id=?', (ref, attempt_id)).fetchone()
        if not row:
            continue
        doc = json.loads(row[0])
        if scope['operation']=='quote_snapshot':
            from .source_adapters import validate_quote_document
            validate_quote_document(doc,scope)
        else:validate_market_document(doc, scope)
        values = doc['values']
        if scope['operation']=='quote_snapshot':
            stamp=doc.get('data_as_of')
            values={k:float(values[k]) for k in ('price','change','change_percent')}
        elif scope['operation'] == 'market_quote':
            values = values['items'][0]
            stamp = values.get('as_of')
        elif scope['operation'] == 'market_technical':
            stamp = values.get('through')
            indicators = values.get('indicators', {})
            values = {'rsi_14': indicators.get('rsi', {}).get('rsi14'),
                      'macd_hist': indicators.get('macd', {}).get('hist')}
        else:
            continue
        try:
            when = datetime.fromisoformat(stamp)
            if scope['operation'] in {'quote_snapshot','market_quote'} and when.tzinfo is None:continue
            candidates.append((when.timestamp() if when.tzinfo else when.toordinal(),ref,values))
        except (ValueError, TypeError):continue
    if not candidates:return output
    latest = max(x[0] for x in candidates)
    selected = [(ref, values) for stamp,ref,values in candidates if stamp==latest]
    # 引用顺序不能改变条件值；同时间不同来源值冲突时保留未知。
    for metric, (_, unit) in METRICS.items():
        numbers = [values.get(metric) for _,values in selected]
        if all(type(v) in (int,float) and math.isfinite(v) for v in numbers) and len(set(numbers))==1:
            output[metric] = {'value':numbers[0], 'unit':unit, 'method_version':'quote_snapshot_v1' if scope['operation']=='quote_snapshot' else 'market_v1',
                              'evidence_refs':sorted({ref for ref,_ in selected})}
    return output
