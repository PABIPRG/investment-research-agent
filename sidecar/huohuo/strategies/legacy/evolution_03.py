# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .evolution_shared import EvolutionPreviewConflict, EvolutionStrategyNotFound, JsonStore, _CLOSED_LOOP_RUNTIME_KEY, _CURRENT_PREVIEW_KEY, _EVOLUTION_LOCK, _MUTABLE_KINDS, _PREVIEW_COLLECTION, _PREVIEW_TTL_SECONDS, _STRATEGY_ID_PATTERN, _str2md5, datetime, hashlib, json, re, secrets, settings, threading, time

def _mutate_symbols(symbols, branch: int) -> list[str]:
    syms = [str(x) for x in symbols or [] if str(x)]
    if not syms:
        return []
    if branch == 0 or len(syms) <= 1:
        return list(syms)
    return syms[:min(2, len(syms))]

def _family_migrate(kind: str, branch: int) -> tuple[str | None, dict | None, str]:
    """生态位族内迁移（P2）：把打法换到同族另一 kind（带该 kind 的变异默认参数）。

    无同族备选 → 返回 (None, None, "")，调用方退化为参数微扰。branch 决定选族内第几个备选，
    保证同一母体同 branch 产出确定（child_id 稳定、幂等）。
    """
    from .evolution_02 import _mutate_params
    from . import genome
    alts = genome.family_alternatives(kind)
    if not alts:
        return (None, None, '')
    alt = alts[branch % len(alts)]
    params = _mutate_params(alt, None, branch)
    note = f'生态位内换打法 {kind}→{alt}（{genome.family_of(kind)} 族备选）'
    return (alt, params, note)

def _pool_migrated_symbols(store: JsonStore, rec: dict, parent_symbols, branch: int) -> list[str] | None:
    """跨同类事件池换/扩标的（P2 泛化验证）：从 gene.scope.pool_ref 定位的同类事件历史候选池取票。

    母体无 gene.scope.pool_ref、或账本无同类历史候选 → 返回 None，调用方保留 v1 截短逻辑。
    返回 保留的母体至多 2 票 + 池内（排除母体已持）新增票，总量上限 EVOLVE_POOL_MAX_NEW_SYMBOLS。
    """
    from . import genome
    from .ledger import event_type_of
    scope = genome.pool_scope(rec)
    event_type = scope.get('event_type')
    direction = scope.get('direction')
    if not event_type:
        return None
    parent = [str(s) for s in parent_symbols or [] if str(s)]
    keep = list(parent[:min(2, len(parent))])
    try:
        from .ledger import symbol_pool
        pool = symbol_pool(store, event_type=event_type, direction=direction, max_symbols=int(settings.evolve_pool_max_new_symbols), exclude=parent)
    except Exception:
        return None
    if not pool:
        return None
    combined = list(dict.fromkeys(keep + [str(s) for s in pool]))
    return combined[:max(len(keep), len(combined))]

def _series_by_sid_map(store: JsonStore) -> dict[str, dict[str, float]]:
    """每 active 策略影子净值序列 → {sid: {date: nav}}，供停滞/相关性判据。"""
    from .evolution_02 import _per_strategy_series, _shadow_series
    return {sid: {p['date']: p['nav'] for p in pts} for sid, pts in _per_strategy_series(_shadow_series(store)[0]).items()}

def _clone_crowded(store: JsonStore, rec: dict, sid: str, nav_series: dict[str, dict[str, float]] | None) -> bool:
    """P4 生态位相关性去重：本 promote 的生态位是否已被「更优的高相关同族」占据。

    该策略(nav 现值) ≤ 同生态位且相关系数 ≥ EVOLVE_CORRELATION_MAX 的某在位 active
    → 视为克隆让位（不产新变异，防克隆膨胀）。样本不足/无同族更优 → False。
    """
    if not nav_series:
        return False
    from . import governance as _gov, genome as _gm
    mine = nav_series.get(sid)
    if not mine:
        return False
    my_vals = [float(v) for v in mine.values()]
    if not my_vals:
        return False
    my_last = my_vals[-1]
    my_scope = _gm.pool_scope(rec)
    my_key = _gov.niche_key(rec.get('kind'), event_type=(my_scope or {}).get('event_type'), direction=rec.get('direction'))
    for other_sid, rec2 in (store.all('strategies') or {}).items():
        if not isinstance(rec2, dict) or str(other_sid) == str(sid):
            continue
        if rec2.get('status') != 'active':
            continue
        if str(rec2.get('mutated_from') or '') == str(sid):
            continue
        o_scope = _gm.pool_scope(rec2)
        if _gov.niche_key(rec2.get('kind'), event_type=(o_scope or {}).get('event_type'), direction=rec2.get('direction')) != my_key:
            continue
        theirs = nav_series.get(other_sid)
        if not theirs:
            continue
        common = sorted(set(mine) & set(theirs))
        if len(common) < settings.evolve_min_days:
            continue
        corr = _gov.shadow_correlation(dict(mine), dict(theirs))
        if corr is None:
            continue
        o_last = float(list(theirs.values())[-1])
        if _gov.clone_blocked(corr, getattr(settings, 'evolve_correlation_max', 0.8), candidate_better=my_last > o_last):
            return True
    return False

def _emit_crossover(actions: list[dict], rec_a: dict, rec_b: dict, child_id: str) -> dict | None:
    """把亲本 A(因子结构) × B(标的池) 重组成一条带双亲谱系的子代 action。"""
    from . import recombine as _rc
    try:
        child = _rc.crossover(rec_a.get('kind'), rec_a.get('params') or {}, rec_b.get('symbols'), rec_a.get('direction'), parent_a=str(rec_a.get('id') or rec_a.get('sid')), parent_b=str(rec_b.get('id') or rec_b.get('sid')))
    except Exception:
        return None
    if not child:
        return None
    action = {'type': 'mutate', 'parent': str(rec_a.get('id') or rec_a.get('sid')), 'parent_b': str(rec_b.get('id') or rec_b.get('sid')), 'sid': child_id, 'kind': child['kind'], 'direction': child['direction'], 'symbols': child['symbols'], 'params': child['params'], 'name': f"{rec_a.get('name') or '亲本A'} × {rec_b.get('name') or '亲本B'} · 重组", 'attribution_note': f"有性繁殖重组：{child['kind']} 因子（亲本A {child['parent_a']}）× 标的池（亲本B {child['parent_b']}，{len(child['symbols'])} 票）", 'reason': f"由“{rec_a.get('name') or '亲本A'}”与“{rec_b.get('name') or '亲本B'}”交叉重组，新候选需重新回测验证"}
    actions.append(action)
    return action

def _maybe_crossover(store: JsonStore, actions: list[dict], strats: dict) -> None:
    """P3 有性繁殖：本批 ≥N 条 promote 亲本时，取两条同向亲本产出 1 条重组子代。

    默认 EVOLVE_RECOMBINE_ENABLED=false → 无动作；开启也只是在 promote 的变异子代
    之外**追加**一条带双亲谱系的子代，不动既有 mutate 分支（防行为漂移）。
    """
    promos = [a for a in actions if a['type'] == 'promote']
    need = max(2, int(getattr(settings, 'evolve_recombine_min_parents', 2)))
    if len(promos) < need:
        return
    cands = []
    for a in promos:
        rec = strats.get(a['sid']) or {}
        if not isinstance(rec, dict) or not rec.get('kind') or (not rec.get('symbols')) or rec.get('verification_status')!='passed' or (rec.get('backtest') or {}).get('thresholds_pass') is not True:
            continue
        cands.append(rec)
    if len(cands) < need:
        return
    used: set[str] = set()
    for i, rec_a in enumerate(cands):
        if str(rec_a.get('id') or rec_a.get('sid')) in used:
            continue
        for rec_b in cands[i + 1:]:
            if str(rec_b.get('id') or rec_b.get('sid')) in used:
                continue
            da, db = (rec_a.get('direction'), rec_b.get('direction'))
            if da and db and (da != db):
                continue
            aid = str(rec_a.get('id') or rec_a.get('sid'))
            bid = str(rec_b.get('id') or rec_b.get('sid'))
            used.update((aid, bid))
            child_id = _child_id(aid, rec_a.get('kind'), {**(rec_a.get('params') or {}), '_x': bid}, 7)
            _emit_crossover(actions, rec_a, rec_b, child_id)
            return

def _child_id(parent: str, kind: str, params: dict, branch: int) -> str:
    key = f'{parent}:{kind}:{hashlib.md5(str(params).encode()).hexdigest()}:{branch}'
    return 'strat-' + _str2md5(key)

def evolve(store: JsonStore | None=None, apply: bool=False, preview_token: str | None=None, strategy_id: str | None=None) -> dict:
    """T→W→H 主循环。写入只能应用已绑定当时状态的精确预案。

    规则（护栏 3 可配置）：
      - nav ≤ retire_nav          → retired（淘汰）
      - 平仓胜率 < 阈值 且 ≥3 笔平仓 → retired
      - nav ≤ demote_nav          → watch（降级观察，仍跑影子、不推荐）
      - nav ≥ promote_nav         → tier=2（升级）+ 若样本外达标且在冷却期外 → 变异回流候选
    """
    from .evolution_01 import _discard_current_preview, _preview_scope, _source_version, _store_preview, _validate_strategy_id
    from .evolution_04 import _apply_preview, _build_preview
    _validate_strategy_id(strategy_id)
    store = store or JsonStore()
    if apply:
        return _apply_preview(store, preview_token, strategy_id)
    with _EVOLUTION_LOCK:
        version_before = _source_version(store, strategy_id)
        response = _build_preview(store, strategy_id)
        version_after = _source_version(store, strategy_id)
        if version_before != version_after:
            raise EvolutionPreviewConflict('进化数据在生成预案时已变化，请重新生成后再确认')
        if response.get('status') != 'ready':
            _discard_current_preview(store, strategy_id)
            return {**response, **_preview_scope(strategy_id), 'preview_status': 'blocked'}
        if not response.get('actions'):
            _discard_current_preview(store, strategy_id)
            return {**response, **_preview_scope(strategy_id), 'preview_status': 'empty'}
        return _store_preview(store, response, version_after, strategy_id)
