# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .evolution_shared import EvolutionPreviewConflict, EvolutionStrategyNotFound, JsonStore, _CLOSED_LOOP_RUNTIME_KEY, _CURRENT_PREVIEW_KEY, _EVOLUTION_LOCK, _MUTABLE_KINDS, _PREVIEW_COLLECTION, _PREVIEW_TTL_SECONDS, _STRATEGY_ID_PATTERN, _str2md5, datetime, hashlib, json, re, secrets, settings, threading, time

def _apply_action(store: JsonStore, a: dict) -> None:
    """把单个 action 落到 strategies 集合（写库）。"""
    from .evolution_01 import _now
    ts = _now()
    if a['type'] in ('promote', 'demote', 'retire'):
        sid = a['sid']

        def apply_transition(current):
            rec = dict(current or {})
            ev = dict(rec.get('evolve') or {})
            if a['type'] == 'promote':
                ev.update({'tier': 2, 'state': 'active', 'updated_at': ts, 'note': a['reason']})
            elif a['type'] == 'demote':
                ev.update({'state': 'watch', 'updated_at': ts, 'note': a['reason']})
            else:
                ev.update({'state': 'retired', 'updated_at': ts, 'note': a['reason']})
                rec['status'] = 'retired'
                rec['retire_reason'] = a['reason']
            if isinstance(a.get('fitness'), dict):
                ev['fitness'] = a['fitness']
            rec['evolve'] = ev
            return rec
        store.mutate('strategies', sid, apply_transition)
        if a['type'] == 'retire' and bool(getattr(settings, 'evolve_archive_enabled', False)):
            from . import gene_archive as _arch
            _arch.archive_record(store, store.get('strategies', sid) or {}, reason=a.get('reason') or 'retire')
    elif a['type'] == 'mutate':
        generation = 1

        def mark_parent(current):
            nonlocal generation
            parent = dict(current or {})
            generation = int(parent.get('generation') or 0) + 1
            pev = dict(parent.get('evolve') or {})
            pev['mutated_at'] = ts
            parent['evolve'] = pev
            return parent
        store.mutate('strategies', a['parent'], mark_parent)
        try:
            from . import genome
            meta: dict = {}
            if a.get('attribution_note'):
                meta['attribution_note'] = a['attribution_note']
            if a.get('parent') and a.get('parent_b'):
                meta['parent_a'] = a['parent']
                meta['parent_b'] = a['parent_b']
            child_gene = genome.gene_for(a['kind'], a['params'], a['symbols'], a['direction'], meta=meta or None)
        except Exception:
            child_gene = None
        rec = {'id': a['sid'], 'name': a['name'], 'kind': a['kind'], 'direction': a['direction'], 'symbols': a['symbols'], 'params': a['params'], 'gene': child_gene, 'status': 'candidate', 'verification_status': 'insufficient', 'source': 'evolution', 'mutated_from': a['parent'], 'generation': generation, 'backtest': {}, 'evolve': {'state': 'active', 'tier': 1, 'updated_at': ts, 'note': f"由 {a['parent']} 变异生成，待回测验证（W→H 回流）"}, 'created_at': ts}
        store.set('strategies', a['sid'], rec)

def _lifecycle_entry(record: dict) -> dict:
    return {'strategy_id': record.get('id'), 'name': record.get('name'), 'kind': record.get('kind'), 'tier': int((record.get('evolve') or {}).get('tier') or 1), 'symbols': record.get('symbols'), 'mutated_from': record.get('mutated_from'), 'source': record.get('source')}

def _lifecycle(store: JsonStore, strategy_id: str | None=None) -> dict[str, list[dict]]:
    from .evolution_02 import _strategy_record
    groups = {key: [] for key in ('active', 'candidate', 'retired', 'watch', 'rejected')}
    for record in (store.all('strategies') or {}).values():
        if not isinstance(record, dict):
            continue
        entry = _lifecycle_entry(record)
        status_value = str(record.get('status') or '')
        evolve_state = str((record.get('evolve') or {}).get('state') or '')
        if status_value in groups:
            groups[status_value].append(entry)
        if status_value == 'active' and evolve_state in {'watch', 'retired'}:
            groups[evolve_state].append(entry)
    if strategy_id is None:
        return groups
    _strategy_record(store, strategy_id)
    all_entries = {str(entry.get('strategy_id')): entry for entries in groups.values() for entry in entries}
    related = {strategy_id}
    changed = True
    while changed:
        changed = False
        for sid, entry in all_entries.items():
            parent = str(entry.get('mutated_from') or '')
            if sid in related and parent and (parent not in related):
                related.add(parent)
                changed = True
            if parent in related and sid not in related:
                related.add(sid)
                changed = True
    return {key: [entry for entry in entries if str(entry.get('strategy_id')) in related] for key, entries in groups.items()}

def record_closed_loop_run(store: JsonStore, *, run_at: str, status_value: str, action_count: int) -> dict:
    """在既有进化审计集合中保存最近一次真实闭环运行，不创建平行状态。"""
    parsed = datetime.fromisoformat(run_at)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('run_at 必须是带时区的 ISO-8601 时间')
    if status_value not in {'completed', 'partial', 'failed'}:
        raise ValueError(f'非法闭环运行状态: {status_value}')
    record = {'recent_run_at': parsed.isoformat(timespec='seconds'), 'status': status_value, 'action_count': max(0, int(action_count))}
    store.set(_PREVIEW_COLLECTION, _CLOSED_LOOP_RUNTIME_KEY, record)
    return record

def _evolution_counts(strategies: dict) -> dict[str, int]:
    """把权威 lifecycle/evolve 字段投影为互斥的四类首屏摘要。"""
    from .evolution_03 import evolve
    counts = {'normal': 0, 'watch': 0, 'promote': 0, 'retire': 0}
    for record in strategies.values():
        if not isinstance(record, dict):
            continue
        lifecycle = str(record.get('status') or '')
        evolve = record.get('evolve')
        evolve = evolve if isinstance(evolve, dict) else {}
        evolve_state = str(evolve.get('state') or '')
        try:
            tier = int(evolve.get('tier') or 1)
        except (TypeError, ValueError):
            tier = 1
        if lifecycle == 'retired' or evolve_state == 'retired':
            counts['retire'] += 1
        elif lifecycle == 'active' and evolve_state == 'watch':
            counts['watch'] += 1
        elif lifecycle == 'active' and tier >= 2:
            counts['promote'] += 1
        elif lifecycle == 'active':
            counts['normal'] += 1
    return counts

def status(store: JsonStore | None=None, strategy_id: str | None=None, include_history: bool=True) -> dict:
    """闭环状态：数据是否就绪 + 生命周期统计。"""
    from .evolution_01 import _last_applied_at, _now, _validate_strategy_id
    from .evolution_02 import _recent_applied, _scoped_shadow_series, _strategy_record, attribution
    from .evolution_04 import _per_strategy_decisions
    _validate_strategy_id(strategy_id)
    store = store or JsonStore()
    _, n = _scoped_shadow_series(store, strategy_id)
    strats = {strategy_id: _strategy_record(store, strategy_id)} if strategy_id is not None else store.all('strategies') or {}
    lifecycle = _lifecycle(store, strategy_id)
    counts = {key: len(entries) if strategy_id is None else sum((str(entry.get('strategy_id')) == strategy_id for entry in entries)) for key, entries in lifecycle.items()}
    ready = n >= settings.evolve_min_days
    if ready:
        per_strategy, _ = _per_strategy_decisions(store, attribution(store, strategy_id), strategy_id)
    else:
        per_strategy = []
    covered = {p['strategy_id'] for p in per_strategy}
    for s in strats.values():
        if not isinstance(s, dict):
            continue
        if s.get('status') != 'active':
            continue
        if s.get('id') in covered:
            continue
        ev = s.get('evolve') or {}
        per_strategy.append({'strategy_id': s.get('id'), 'name': s.get('name'), 'kind': s.get('kind'), 'tier': int(ev.get('tier') or 1), 'symbols': s.get('symbols'), 'nav': None, 'closed_win_rate_pct': None, 'closed_trades': 0, 'decision': 'none', 'reason': '影子数据不足，暂不参与判定' if s.get('status') == 'active' else f"策略当前状态为 {s.get('status') or 'unknown'}，仅展示历史证据", 'behavior': '待判定' if s.get('status') == 'active' else '不参与当前判定'})
    runtime = store.get(_PREVIEW_COLLECTION, _CLOSED_LOOP_RUNTIME_KEY) or {}
    from .scheduler import next_closed_loop_run_at
    last_applied = _last_applied_at(store, strategy_id)
    return {'as_of': _now(), 'days_of_data': n, 'min_days': settings.evolve_min_days, 'ready': ready, 'counts': counts, 'evolution_counts': _evolution_counts(strats), 'lifecycle': lifecycle, 'note': None if ready else f'影子净值仅 {n} 日，自进化待累积至 {settings.evolve_min_days} 日', 'last_applied_at': last_applied, 'closed_loop_enabled': settings.closed_loop_enabled, 'closed_loop_time': settings.closed_loop_time, 'recent_run_at': runtime.get('recent_run_at'), 'next_scheduled_run_at': next_closed_loop_run_at(), 'per_strategy': per_strategy, 'recent_applied': _recent_applied(store, strategy_id=strategy_id, limit=5) if include_history else []}
