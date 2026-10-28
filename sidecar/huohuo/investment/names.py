"""名称属于已确认记录的元数据；目录补充只用于展示，不改投资事实。"""
from ..contracts import Invalid, text
from ..research_entities.security_search import cached_name
from .instruments import annotate


def usable_name(value, code):
    if not isinstance(value, str):
        return None
    name = value.strip()
    return name if name and name != code and name not in {'名称待补充', '证券名称待补全', '未命名证券'} else None


def recorded_names(document):
    names = {}
    for row in document.get('manual_trades', []) + document.get('watchlist', []) + document.get('default', []):
        name = usable_name(row.get('name'), row['ticker'])
        if name:
            names[row['ticker']] = name
    return names


def trade_metadata(document, command, payload):
    values = dict(payload)
    name = values.pop('name', None) if command == 'trade' else None
    if name is not None:
        name = text(name, '证券名称', 100)
        if not usable_name(name, values.get('ticker')):
            raise Invalid('请使用已选择的证券名称；名称未知时保留代码，不填写占位文字')
        previous = next((x for x in document['manual_trades']
                         if x['request_id'] == payload.get('request_id')), None)
        if previous and previous.get('name') != name:
            raise Invalid('同一成交编号不能变更证券名称；请通过资料校正处理')
    return values, name


def restore_names(document, previous, command, payload, name, result):
    names = recorded_names(previous)
    if command == 'trade' and name:
        names[payload['ticker']] = name
        entry = next(x for x in document['manual_trades'] if x['request_id'] == payload['request_id'])
        entry['name'] = name
        result['entry']['name'] = name
    for row in document['default']:
        if names.get(row['ticker']):
            row['name'] = names[row['ticker']]


def display_rows(rows, names):
    result = []
    for row in rows:
        stored = usable_name(row.get('name'), row['ticker']) or names.get(row['ticker'])
        public = cached_name(row['ticker']) if not stored else None
        result.append({**annotate(row),
                       'display_name': stored or (public['name'] if public else None),
                       'name_source': 'recorded' if stored else 'security_directory' if public else 'unavailable'})
    return result
