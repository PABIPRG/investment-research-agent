# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .evolution_shared import EvolutionPreviewConflict, EvolutionStrategyNotFound, JsonStore, _CLOSED_LOOP_RUNTIME_KEY, _CURRENT_PREVIEW_KEY, _EVOLUTION_LOCK, _MUTABLE_KINDS, _PREVIEW_COLLECTION, _PREVIEW_TTL_SECONDS, _STRATEGY_ID_PATTERN, _str2md5, datetime, hashlib, json, re, secrets, settings, threading, time

def _validate_strategy_id(strategy_id: str | None) -> None:
    """在任何 scoped 存储访问前拒绝非法策略标识。"""
    if strategy_id is not None and (not _STRATEGY_ID_PATTERN.fullmatch(strategy_id)):
        raise ValueError('strategy_id must be a safe identifier')

def _scope_key(strategy_id: str | None) -> str:
    return 'global' if strategy_id is None else f'strategy:{strategy_id}'

def _current_preview_key(strategy_id: str | None) -> str:
    return f'_current:{_scope_key(strategy_id)}'

def _preview_scope(strategy_id: str | None) -> dict:
    return {'scope_kind': 'global' if strategy_id is None else 'strategy', **({} if strategy_id is None else {'strategy_id': strategy_id})}

def _record_scope(record: dict) -> dict:
    if record.get('scope_kind') == 'strategy':
        return {'scope_kind': 'strategy', 'strategy_id': record.get('strategy_id')}
    return {'scope_kind': 'global'}

def _settings_payload() -> dict:
    return settings.snapshot()

def _hash_source_payload(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()

def _legacy_source_version(store: JsonStore) -> str:
    return _hash_source_payload({'strategies': store.all('strategies') or {}, 'shadow_equity': store.all('shadow_equity') or {}, 'shadows': store.all('shadows') or {}, 'settings': _settings_payload()})

def _record_source_version(store: JsonStore, record: dict, strategy_id: str | None) -> str:
    if strategy_id is None and 'scope_kind' not in record:
        return _legacy_source_version(store)
    return _source_version(store, strategy_id)

def _source_version(store: JsonStore, strategy_id: str | None=None) -> str:
    return _hash_source_payload({'state': store.version(), 'settings': settings.snapshot(), 'scope': _preview_scope(strategy_id)})

def _public_preview(record: dict) -> dict:
    return {key: value for key, value in record.items() if not key.startswith('_')}

def _store_preview(store: JsonStore, response: dict, state_version: str, strategy_id: str | None) -> dict:
    token = secrets.token_hex(16)
    now = time.time()
    record = {**response, **_preview_scope(strategy_id), 'preview_token': token, 'state_version': state_version, 'preview_status': 'pending', 'expires_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now + _PREVIEW_TTL_SECONDS)), '_expires_at_epoch': now + _PREVIEW_TTL_SECONDS}
    current_key = _current_preview_key(strategy_id)
    previous_tokens = [store.get(_PREVIEW_COLLECTION, current_key)]
    if strategy_id is None:
        previous_tokens.append(store.get(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY))
    for previous in previous_tokens:
        if not isinstance(previous, str):
            continue
        old = store.get(_PREVIEW_COLLECTION, previous)
        if isinstance(old, dict) and old.get('preview_status') == 'pending' and (_record_scope(old) == _preview_scope(strategy_id)):
            store.update(_PREVIEW_COLLECTION, previous, preview_status='superseded')
    store.set(_PREVIEW_COLLECTION, token, record)
    store.set(_PREVIEW_COLLECTION, current_key, token)
    if strategy_id is None:
        store.delete(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)
    return _public_preview(record)

def _discard_current_preview(store: JsonStore, strategy_id: str | None) -> None:
    current_key = _current_preview_key(strategy_id)
    token = store.get(_PREVIEW_COLLECTION, current_key)
    if strategy_id is None and (not isinstance(token, str)):
        token = store.get(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)
    if isinstance(token, str):
        record = store.get(_PREVIEW_COLLECTION, token)
        if isinstance(record, dict) and record.get('preview_status') == 'pending':
            store.update(_PREVIEW_COLLECTION, token, preview_status='superseded')
    store.delete(_PREVIEW_COLLECTION, current_key)
    if strategy_id is None:
        store.delete(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)

def current_preview(store: JsonStore | None=None, strategy_id: str | None=None) -> dict:
    """返回模型可读取的当前待确认预案及其有效性，不暴露内部存储字段。"""
    from .evolution_02 import _strategy_record
    _validate_strategy_id(strategy_id)
    store = store or JsonStore()
    if strategy_id is not None:
        _strategy_record(store, strategy_id)
    token = store.get(_PREVIEW_COLLECTION, _current_preview_key(strategy_id))
    if strategy_id is None and (not isinstance(token, str)):
        token = store.get(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)
    record = store.get(_PREVIEW_COLLECTION, token) if isinstance(token, str) else None
    if not isinstance(record, dict) or record.get('preview_status') != 'pending' or _record_scope(record) != _preview_scope(strategy_id):
        return {'preview_status': 'none', 'actions': [], 'count': 0}
    result = _public_preview(record)
    if time.time() > float(record.get('_expires_at_epoch') or 0):
        return {**result, 'preview_status': 'expired', 'valid': False}
    valid = record.get('state_version') == _record_source_version(store, record, strategy_id)
    return {**result, 'preview_status': 'pending' if valid else 'stale', 'valid': valid}

def _now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')

def _last_applied_at(store: JsonStore, strategy_id: str | None=None) -> str | None:
    """最近一次成功应用的进化时间（YYYY-MM-DD HH:MM:SS）；从未应用返回 None。

    扫 evolution_previews 集合里 preview_status=="applied" 的记录取最大 applied_at，
    不依赖当前指针（指针会被新的 pending 预案顶掉）。
    """
    from .evolution_02 import _recent_applied
    rows = _recent_applied(store, strategy_id=strategy_id, limit=1)
    return None if not rows else str(rows[0].get('applied_at') or '') or None
