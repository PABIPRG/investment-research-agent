# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .evolution_shared import EvolutionPreviewConflict, EvolutionStrategyNotFound, JsonStore, _CLOSED_LOOP_RUNTIME_KEY, _CURRENT_PREVIEW_KEY, _EVOLUTION_LOCK, _MUTABLE_KINDS, _PREVIEW_COLLECTION, _PREVIEW_TTL_SECONDS, _STRATEGY_ID_PATTERN, _str2md5, datetime, hashlib, json, re, secrets, settings, threading, time

def _recent_applied(store: JsonStore, strategy_id: str | None=None, limit: int=5) -> list[dict]:
    """最近 N 条已成功应用的进化记录摘要，按 applied_at 降序。

    扫 evolution_previews 集合里 preview_status=="applied" 的记录，
    供前端渲染「最近自动进化」时间线。
    """
    rows: list[dict] = []
    for record in (store.all(_PREVIEW_COLLECTION) or {}).values():
        if not isinstance(record, dict) or record.get('preview_status') != 'applied':
            continue
        actions = [action for action in record.get('actions') or [] if isinstance(action, dict)]
        if strategy_id is not None:
            actions = [action for action in actions if action.get('sid') == strategy_id or action.get('parent') == strategy_id]
        if not actions:
            continue
        rows.append({'applied_at': record.get('applied_at'), 'count': len(actions), 'actions': actions})
    rows.sort(key=lambda row: str(row.get('applied_at') or ''), reverse=True)
    return rows[:limit]

def _parse_ts(ts) -> float | None:
    """'%Y-%m-%d %H:%M:%S' → epoch；解析失败返回 None。"""
    if not ts:
        return None
    try:
        return time.mktime(time.strptime(str(ts).strip(), '%Y-%m-%d %H:%M:%S'))
    except (ValueError, TypeError):
        return None

def _shadow_series(store: JsonStore) -> tuple[list[dict], int]:
    """shadow_equity 按日期升序 → ( [{date, overall_nav, strategies{sid:{nav,…}}}], days )。

    overall_nav 非法/≤0 的日期跳过（幂等跑当日只留一笔）。"""
    eq = store.all('shadow_equity') or {}
    days: list[dict] = []
    for d in sorted(eq.keys()):
        rec = eq[d] or {}
        try:
            ov = float(rec.get('overall_nav') or 0.0)
        except (TypeError, ValueError):
            continue
        if ov > 0:
            days.append({'date': d, 'overall_nav': ov, 'strategies': rec.get('strategies') or {}})
    return (days, len(days))

def _strategy_record(store: JsonStore, strategy_id: str) -> dict:
    from .evolution_01 import _validate_strategy_id
    _validate_strategy_id(strategy_id)
    record = store.get('strategies', strategy_id)
    if not isinstance(record, dict):
        raise EvolutionStrategyNotFound(f'策略 {strategy_id} 不存在')
    return record

def _scoped_shadow_series(store: JsonStore, strategy_id: str | None) -> tuple[list[dict], int]:
    """返回全局或单策略有效影子净值序列。"""
    if strategy_id is None:
        return _shadow_series(store)
    _strategy_record(store, strategy_id)
    scoped: list[dict] = []
    for date in sorted(store.all('shadow_equity') or {}):
        day = store.get('shadow_equity', date)
        if not isinstance(day, dict):
            continue
        strategy = (day.get('strategies') or {}).get(strategy_id)
        if not isinstance(strategy, dict):
            continue
        try:
            nav = float(strategy.get('nav') or 0)
        except (TypeError, ValueError):
            continue
        if nav <= 0:
            continue
        scoped.append({'date': date, 'overall_nav': nav, 'strategies': {strategy_id: strategy}})
    return (scoped, len(scoped))

def _per_strategy_series(days: list[dict]) -> dict[str, list[dict]]:
    """每策略影子净值序列 → {sid: [{date, nav}]}（正数只收，非法跳过）。"""
    out: dict[str, list[dict]] = {}
    for d in days:
        for sid, rec in (d.get('strategies') or {}).items():
            try:
                nav = float((rec or {}).get('nav') or 0.0)
            except (TypeError, ValueError):
                continue
            if nav > 0:
                out.setdefault(sid, []).append({'date': d['date'], 'nav': nav})
    return out

def _max_drawdown(navs: list[float]) -> float | None:
    if len(navs) < 2:
        return None
    peak = navs[0]
    mdd = 0.0
    for v in navs:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd

def _closed_trades(store: JsonStore, sid: str) -> list[dict]:
    rows = store.get('shadows', f'trades:{sid}') or []
    return [t for t in rows if isinstance(t, dict)]

def attribution(store: JsonStore | None=None, strategy_id: str | None=None) -> dict:
    """S→T：影子组合整体归因 + 每策略贡献分解（只读，永不写库）。"""
    from .evolution_01 import _now, _validate_strategy_id
    _validate_strategy_id(strategy_id)
    store = store or JsonStore()
    days, n = _scoped_shadow_series(store, strategy_id)
    base = {'as_of': _now(), 'days_of_data': n, 'min_days': settings.evolve_min_days, 'data_note': None if n >= settings.evolve_min_days else f'影子净值仅 {n} 日，需累积至 {settings.evolve_min_days} 日才开始升降级/变异'}
    if not days:
        return {**base, 'overall': None, 'strategies': []}
    ovN = days[-1]['overall_nav']
    total_ret = ovN - 1.0
    overall = {'start_nav': 1.0, 'end_nav': ovN, 'return_pct': round(total_ret * 100, 2), 'max_drawdown_pct': round(_max_drawdown([d['overall_nav'] for d in days]) * 100, 2) if len(days) >= 2 else None, 'strategy_count': 1 if strategy_id is not None else len({sid for d in days for sid in d.get('strategies') or {}})}
    strats = {strategy_id: _strategy_record(store, strategy_id)} if strategy_id is not None else store.all('strategies') or {}
    series = _per_strategy_series(days)
    per = []
    for sid, pts in series.items():
        s = strats.get(sid) or {}
        navs = [p['nav'] for p in pts]
        s_ret = navs[-1] - 1.0 if navs else None
        trades = _closed_trades(store, sid)
        closed = len(trades)
        wins = sum((1 for t in trades if float(t.get('ret_pct') or 0) > 0))
        cum_ret = sum((float(t.get('ret_pct') or 0) for t in trades))
        per.append({'strategy_id': sid, 'name': s.get('name'), 'kind': s.get('kind'), 'status': s.get('status'), 'symbols': s.get('symbols'), 'nav': navs[-1], 'return_pct': round(s_ret * 100, 2) if s_ret is not None else None, 'max_drawdown_pct': round(_max_drawdown(navs) * 100, 2) if len(navs) >= 2 else None, 'closed_trades': closed, 'closed_win_rate_pct': round(wins / closed * 100, 1) if closed else None, 'closed_cum_return_pct': round(cum_ret, 2) if closed else None})
    per.sort(key=lambda x: -(x['return_pct'] if x['return_pct'] is not None else -999))
    return {**base, 'overall': overall, 'strategies': per}

def _pick_variant(opts: list, cur, branch: int):
    """从候选集取一个与当前值不同的变体（branch 决定向前/向后偏移）。"""
    try:
        i = opts.index(cur)
    except ValueError:
        i = 1 if cur <= opts[0] else len(opts) - 2
    j = i + (1 if branch else -1)
    j = max(0, min(len(opts) - 1, j))
    if j == i:
        j = (i + 1) % len(opts)
    return opts[j]

def _mutate_params(kind: str, base: dict | None, branch: int) -> dict:
    """技术规则参数轻变异（小步长，保持与父策略同构）。"""
    base = dict(base or {})
    if kind == 'ma_cross':
        fast_opts, slow_opts = ([3, 5, 8, 13], [15, 21, 34])
        f = _pick_variant(fast_opts, int(base.get('fast', 5)), branch)
        s = _pick_variant(slow_opts, int(base.get('slow', 20)), branch)
        if f >= s:
            s = min(s + 8, 34)
        return {'fast': f, 'slow': s}
    if kind == 'rsi_reversal':
        n = _pick_variant([7, 10, 14, 21], int(base.get('n', 14)), branch)
        os_ = _pick_variant([25, 30, 35], float(base.get('oversold', 30)), branch)
        ob = _pick_variant([65, 70, 75], float(base.get('overbought', 70)), branch)
        if os_ >= ob:
            ob = min(os_ + 40, 80)
        return {'n': n, 'oversold': os_, 'overbought': ob}
    if kind == 'breakout':
        return {'n': _pick_variant([10, 20, 30, 40], int(base.get('n', 20)), branch)}
    if kind == 'bollinger':
        n = _pick_variant([10, 20, 30], int(base.get('n', 20)), branch)
        k = _pick_variant([1.5, 2.0, 2.5, 3.0], float(base.get('k', 2.0)), branch)
        return {'n': n, 'k': k}
    if kind == 'volume_breakout':
        n = _pick_variant([10, 20, 30], int(base.get('n', 20)), branch)
        vm = _pick_variant([1.2, 1.5, 2.0, 2.5], float(base.get('vol_mult', 1.5)), branch)
        return {'n': n, 'vol_mult': vm}
    return {'n': _pick_variant([5, 10, 20], int(base.get('n', 10)), branch)}
