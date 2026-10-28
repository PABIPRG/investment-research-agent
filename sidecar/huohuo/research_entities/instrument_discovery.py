"""复用本会话成功发现工具的来源记录；不猜证券类型、不读取旧实例。"""
import json
import re

from .models import EntityInstance
from .resolution import DirectoryRepository

SOURCES = {'fund_lookup': {'akshare.fund_name_em'},
           'convertible_bond_lookup': {'akshare.bond_zh_cov_info', 'akshare.bond_zh_cov'}}


def _text(value, maximum=200):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= maximum else None


def _entity(tool, source, row, known):
    if not isinstance(row, dict):
        return None
    if tool == 'fund_lookup':
        code, name = row.get('基金代码'), row.get('基金简称')
        kind, key, prefix = 'ENTITY_01_02', 'fund_code', 'FUND'
        attributes = {'fund_type': _text(row.get('基金类型'))}
    elif source == 'akshare.bond_zh_cov_info':
        code, name = row.get('SECURITY_CODE'), row.get('SECURITY_NAME_ABBR')
        if not re.fullmatch(r'\d{6}', str(row.get('CONVERT_STOCK_CODE', ''))):
            return None
        kind, key, prefix, attributes = 'ENTITY_01_04', 'bond_code', 'BOND', {}
    else:
        code, name = row.get('债券代码'), row.get('债券简称')
        if not re.fullmatch(r'\d{6}', str(row.get('正股代码', ''))):
            return None
        kind, key, prefix, attributes = 'ENTITY_01_04', 'bond_code', 'BOND', {}
    if not isinstance(code, str) or not re.fullmatch(r'\d{6}', code) or not _text(name):
        return None
    base = next((e for e in known.entities.values()
                 if e.entity_type_code == kind and e.identifiers.get(key) == code), None)
    identifiers = dict(base.identifiers) if base else {key: code}
    # 只接受数据源明确给出的市场；开放式基金代码可能与 A 股重合。
    secucode = row.get('SECUCODE')
    if secucode is not None:
        match = re.fullmatch(re.escape(code) + r'\.(SH|SZ)', str(secucode))
        if not match:
            return None
        identifiers['exchange'] = {'SH': 'SSE', 'SZ': 'SZSE'}[match[1]]
    return EntityInstance(entity_id=base.entity_id if base else f'{prefix}:{code}',
        entity_type_code=kind, canonical_name=name.strip(), identifiers=identifiers,
        aliases=list(dict.fromkeys([*(base.aliases if base else []), *([base.canonical_name] if base else [])])),
        attributes={**(base.attributes if base else {}), **attributes}, source=source)


def compose(repo, principal, session, query, catalog, *, ttl=3600):
    """来源限时且绑定主体/会话；模型文本只能匹配，不能提供身份字段。"""
    with repo.connection() as db:
        calls = db.execute('SELECT id,tool_id,result,request,created_at FROM research_tool_calls '
            'WHERE principal=? AND session=? AND tool_id IN (?,?) AND result IS NOT NULL AND created_at>? '
            'ORDER BY created_at DESC,id DESC LIMIT 40',
            (principal, session, *SOURCES, repo.clock()-ttl)).fetchall()
    known, entities, evidence = DirectoryRepository([]), {}, {}
    for call in calls:
        result = json.loads(call['result'])
        arguments = json.loads(call['request'])
        source = result.get('source')
        if result.get('status') != 'ok' or source not in SOURCES[call['tool_id']]:
            continue
        data = result.get('data', {})
        rows = [data['raw']] if call['tool_id'] == 'convertible_bond_lookup' and isinstance(data.get('raw'), dict) else data.get('records', [])
        if not isinstance(rows, list):
            continue
        for row in rows[:1000]:
            entity = _entity(call['tool_id'], source, row, known)
            if entity is None or entity.entity_id in entities:
                continue
            code = entity.identifiers.get('fund_code') or entity.identifiers.get('bond_code')
            by_code = re.search(r'(?<!\d)' + re.escape(code) + r'(?!\d)', query)
            by_name = len(entity.canonical_name) >= 2 and entity.canonical_name in query
            searched = _text(arguments.get('name'))
            by_alias = searched and len(searched) >= 2 and searched in query and searched in entity.canonical_name
            if not by_code and not by_name and not by_alias:
                continue
            if by_alias:
                entity.aliases = list(dict.fromkeys([*entity.aliases, searched]))
            entities[entity.entity_id] = entity
            evidence[entity.entity_id] = {'evidence_id': call['id'], 'source': source,
                'created_at': call['created_at'], 'expires_at': call['created_at'] + ttl}
    if not entities:
        return catalog
    # 来源目录失败时只保留已成功读取的发现记录，不能挟带过期股票候选。
    healthy = catalog.get('status') == 'ok'
    expiry = min(x['expires_at'] for x in evidence.values())
    if healthy and catalog.get('expires_at'):
        expiry = min(expiry, catalog['expires_at'])
    return {**catalog, 'rows': catalog['rows'] if healthy else [], 'status': 'ok',
        'source': {'provider': '同会话已读取的公开证券资料', 'directory': catalog.get('source'),
                   'directory_available': healthy}, 'expires_at': expiry,
        'discovered_entities': list(entities.values()), 'discovered_evidence': evidence}
