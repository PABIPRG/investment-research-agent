# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .evolution_shared import EvolutionPreviewConflict, EvolutionStrategyNotFound, JsonStore, _CLOSED_LOOP_RUNTIME_KEY, _CURRENT_PREVIEW_KEY, _EVOLUTION_LOCK, _MUTABLE_KINDS, _PREVIEW_COLLECTION, _PREVIEW_TTL_SECONDS, _STRATEGY_ID_PATTERN, _str2md5, datetime, hashlib, json, re, secrets, settings, threading, time

def _per_strategy_decisions(store: JsonStore, attr: dict, strategy_id: str | None=None) -> tuple[list[dict], list[dict]]:
    """为每个 active 策略生成当前判定条目 + 判定触发的动作列表。

    纯代码搬移自原 _build_preview 的分策略循环，输出逐字节不变，
    供 _build_preview（preview 预案）与 status（闭环看板）复用。
    """
    from .evolution_02 import _mutate_params, _parse_ts, _strategy_record
    from .evolution_03 import _child_id, _clone_crowded, _family_migrate, _maybe_crossover, _mutate_symbols, _pool_migrated_symbols, _series_by_sid_map
    actions: list[dict] = []
    strats = {strategy_id: _strategy_record(store, strategy_id)} if strategy_id is not None else store.all('strategies') or {}
    now = time.time()
    cooldown = settings.evolve_mutate_cooldown_days * 86400
    _nav_series = _series_by_sid_map(store)
    valid_days = {sid:len(points) for sid,points in _nav_series.items()}
    _cur_regime = None
    if bool(getattr(settings, 'evolve_hibernate_enabled', False)):
        from . import regime as _rg
        _rr = _rg.latest_regime(store)
        _cur_regime = (_rr or {}).get('regime') if isinstance(_rr, dict) else None
    per_strategy: list[dict] = []
    for s in attr['strategies']:
        sid = s['strategy_id']
        rec = strats.get(sid) or {}
        if not isinstance(rec, dict):
            continue
        ev = rec.get('evolve') or {}
        nav = s['nav']
        winr = s['closed_win_rate_pct']
        closed = s['closed_trades'] or 0
        tier = int(ev.get('tier') or 1)
        entry: dict = {'strategy_id': sid, 'name': rec.get('name'), 'kind': rec.get('kind'), 'tier': tier, 'symbols': rec.get('symbols'), 'nav': nav, 'closed_win_rate_pct': winr, 'closed_trades': closed, 'decision': 'none', 'reason': '', 'behavior': '正常运行'}
        if rec.get('status') != 'active':
            continue
        if valid_days.get(sid,0) < settings.evolve_min_days:
            entry.update(decision='none',behavior='等待样本',reason=f"本策略仅 {valid_days.get(sid,0)} 个有效影子日期，需至少 {settings.evolve_min_days} 日，不生成进化动作")
            per_strategy.append(entry)
            continue
        if _cur_regime and bool(getattr(settings, 'evolve_hibernate_enabled', False)):
            from . import genome as _gm
            allow = ((_gm.read_gene(rec) or {}).get('regime_gate') or {}).get('allow') or []
            if _cur_regime not in allow:
                entry.update(decision='hold', behavior='冬眠', reason=f'市场 regime={_cur_regime} 不在该策略适配区，暂停触发；环境不配合不计能力，不因这段做升/降/汰')
                per_strategy.append(entry)
                continue
        from . import fitness as _fit
        fitness_mode = str(getattr(settings, 'evolve_fitness_mode', 'log') or 'log').lower()
        bt_rec = rec.get('backtest')
        extended = bt_rec.get('extended_backtest') if isinstance(bt_rec, dict) else None
        cohort = [r['nav'] for r in attr['strategies'] if isinstance(r, dict) and r.get('nav') is not None and valid_days.get(r['strategy_id'],0)>=settings.evolve_min_days]
        eff = _fit.effective_lines(nav=nav, peer_navs=cohort, mode=fitness_mode, min_peers=settings.evolve_relative_min_peers, promote_nav=settings.evolve_promote_nav, demote_nav=settings.evolve_demote_nav, retire_nav=settings.evolve_retire_nav, promote_percentile=settings.evolve_promote_percentile, retire_percentile=settings.evolve_retire_percentile)
        overfit = _fit.overfit_of(extended, gap_pct=settings.evolve_overfit_gap_pct, min_trades=settings.evolve_overfit_min_trades)
        entry['fitness'] = _fit.compute_profile(nav=nav, peer_navs=cohort, mode=fitness_mode, min_peers=settings.evolve_relative_min_peers, promote_nav=settings.evolve_promote_nav, demote_nav=settings.evolve_demote_nav, retire_nav=settings.evolve_retire_nav, promote_percentile=settings.evolve_promote_percentile, retire_percentile=settings.evolve_retire_percentile, extended=extended, overfit_gap_pct=settings.evolve_overfit_gap_pct, overfit_min_trades=settings.evolve_overfit_min_trades)
        _retire_line, _demote_line, _promote_line = (eff['retire_nav'], eff['demote_nav'], eff['promote_nav'])
        if overfit.get('flag'):
            _promote_line = float('inf')
        if nav is not None and nav <= _retire_line and (ev.get('state') != 'retired'):
            reason = f'影子净值 {nav:.4f} ≤ 淘汰线 {settings.evolve_retire_nav}'
            entry.update(decision='retire', behavior='淘汰', reason=reason)
            actions.append({'type': 'retire', 'sid': sid, 'from': ev.get('state') or 'active', 'to': 'retired', 'reason': reason, 'fitness': entry['fitness']})
            per_strategy.append(entry)
            continue
        if winr is not None and winr < settings.evolve_retire_closed_win * 100 and (closed >= 3) and (ev.get('state') != 'retired'):
            reason = f'平仓胜率 {winr:.0f}% < {settings.evolve_retire_closed_win * 100:.0f}%（已平 {closed} 笔），影子表现不可靠'
            entry.update(decision='retire', behavior='淘汰', reason=reason)
            actions.append({'type': 'retire', 'sid': sid, 'from': ev.get('state') or 'active', 'to': 'retired', 'reason': reason, 'fitness': entry['fitness']})
            per_strategy.append(entry)
            continue
        if _nav_series is not None and bool(getattr(settings, 'evolve_stagnant_enabled', False)) and (ev.get('state', 'active') == 'active') and (rec.get('status') == 'active'):
            own = _nav_series.get(sid) or {}
            if own and len(own) > int(getattr(settings, 'evolve_stagnant_days', 10)):
                from . import governance as _gov
                if _gov.stagnant(own, stale_days=int(getattr(settings, 'evolve_stagnant_days', 10))):
                    reason = f'连续 {settings.evolve_stagnant_days} 天未刷新影子净值新高（现 {nav:.4f}），长期平庸让位'
                    entry.update(decision='retire', behavior='淘汰·停滞', reason=reason)
                    actions.append({'type': 'retire', 'sid': sid, 'from': ev.get('state') or 'active', 'to': 'retired', 'reason': reason, 'stagnant': True, 'fitness': entry['fitness']})
                    per_strategy.append(entry)
                    continue
        if nav is not None and nav <= _demote_line and (ev.get('state', 'active') == 'active'):
            reason = f'影子净值 {nav:.4f} ≤ 观察线 {settings.evolve_demote_nav}，降级为观察（停止推荐、继续跑影子）'
            entry.update(decision='demote', behavior='降级观察', reason=reason)
            actions.append({'type': 'demote', 'sid': sid, 'from': 'active', 'to': 'watch', 'reason': reason, 'fitness': entry['fitness']})
            per_strategy.append(entry)
            continue
        if nav is not None and nav >= _promote_line and (not overfit.get('flag')) and (tier < 2):
            reason = f'影子净值 {nav:.4f} ≥ 升级线 {settings.evolve_promote_nav}'
            entry.update(decision='promote', behavior='升级', reason=reason)
            actions.append({'type': 'promote', 'sid': sid, 'from': f'tier{tier}', 'to': 'tier2', 'reason': reason, 'fitness': entry['fitness']})
            oos_ok = rec.get('verification_status') == 'passed' and (rec.get('backtest') or {}).get('thresholds_pass') is True
            last_m = ev.get('mutated_at')
            cooled = not last_m or now - (_parse_ts(last_m) or now) > cooldown
            _crowded = bool(getattr(settings, 'evolve_correlation_enabled', False)) and bool(_clone_crowded(store, rec, sid, _nav_series))
            if oos_ok and cooled and (not _crowded):
                kind = rec.get('kind')
                migration_on = bool(getattr(settings, 'evolve_migration_enabled', False))
                from_branch = int(getattr(settings, 'evolve_migrate_from_branch', 1))
                for b in range(settings.evolve_mutate_branches):
                    if kind not in _MUTABLE_KINDS:
                        break
                    child_kind, child_params, a_note = (kind, None, '')
                    migrated_family = False
                    if migration_on and b >= from_branch:
                        alt_kind, alt_params, fam_note = _family_migrate(kind, b)
                        if alt_kind:
                            child_kind, child_params, a_note = (alt_kind, alt_params, fam_note)
                            migrated_family = True
                    params = child_params if migrated_family else _mutate_params(child_kind, rec.get('params'), b)
                    symbols = _mutate_symbols(rec.get('symbols'), b)
                    if migration_on and b >= from_branch:
                        pool_syms = _pool_migrated_symbols(store, rec, rec.get('symbols'), b)
                        if pool_syms:
                            symbols = pool_syms
                            a_note = (a_note + '；' if a_note else '') + f'跨同类事件池换标的（历史候选 {len(symbols)} 票）'
                    if bool(getattr(settings, 'evolve_guided_prune_enabled', False)) and isinstance(extended, dict) and isinstance(extended.get('per_symbol'), dict) and extended['per_symbol']:
                        from . import recombine as _rc
                        _scores = _rc.evidence_scores(extended.get('per_symbol') or {})
                        if _scores:
                            _before = list(symbols)
                            symbols = _rc.prune_losers(symbols, _scores, drop_worst=int(getattr(settings, 'evolve_guided_prune_worst', 1)))
                            if len(symbols) < len(_before):
                                a_note = (a_note + '；' if a_note else '') + f'归因剪枝换掉拖累票 {len(_before) - len(symbols)} 只'
                    nsid = _child_id(sid, child_kind, params, b)
                    if nsid in strats:
                        continue
                    actions.append({'type': 'mutate', 'parent': sid, 'sid': nsid, 'kind': child_kind, 'direction': rec.get('direction'), 'symbols': symbols, 'params': params, 'name': f"{rec.get('name') or '研究策略'} · 变体{b+1}", 'attribution_note': a_note or None, 'reason': f"由“{rec.get('name') or '研究策略'}”派生；新候选需重新回测验证" + (f'；{a_note}' if a_note else '')})
            if any((a.get('type') == 'mutate' and a.get('parent') == sid for a in actions)):
                entry.update(behavior='升级+变异')
            per_strategy.append(entry)
            continue
        if nav is None:
            entry.update(behavior='待判定', reason='影子净值缺失，暂不参与判定')
        elif tier >= 2:
            entry.update(behavior='已升级', reason=f'影子净值 {nav:.4f}，已升级至 tier2，不重复升级')
        elif ev.get('state') == 'watch':
            entry.update(behavior='降级观察中', reason=f'影子净值 {nav:.4f} ≤ 观察线 {settings.evolve_demote_nav}，已在 watch 观察')
        else:
            _f = entry.get('fitness') or {}
            _abs_v = (_f.get('absolute') or {}).get('verdict')
            _fin = _f.get('decision')
            _pct = _f.get('percentile')
            if _abs_v in ('promote',) and _fin == 'hold':
                if overfit.get('flag'):
                    entry.update(behavior='过拟合不升', reason=f'样本内胜率虚高（IS−OOS ≥ {settings.evolve_overfit_gap_pct:.0f}pp），仅样本内好看，不升级')
                elif _pct is not None:
                    entry.update(behavior='跟风不升', reason=f'绝对净值过线但同批分位 {_pct}% 未达 {settings.evolve_promote_percentile:.0f}%，判为跟随行情而非真本事，不升级')
                else:
                    entry.update(behavior='正常运行', reason='绝对线达标，暂无进一步动作')
            elif _abs_v in ('retire', 'demote') and _fin == 'hold' and (_pct is not None):
                entry.update(behavior='抗跌豁免', reason=f'净值跌破 v1 观察/淘汰线但同批分位 {_pct}%（高位抗跌），判为行情拖累而非能力问题，暂不降级/淘汰')
            else:
                entry.update(behavior='正常运行', reason=f'影子净值 {nav:.4f} 处于 {settings.evolve_demote_nav}~{settings.evolve_promote_nav} 带内，无升降级动作')
        per_strategy.append(entry)
    if bool(getattr(settings, 'evolve_recombine_enabled', False)):
        _maybe_crossover(store, actions, strats)
    return (per_strategy, actions)

def _build_preview(store: JsonStore, strategy_id: str | None=None) -> dict:
    from .evolution_01 import _last_applied_at, _now
    from .evolution_02 import _scoped_shadow_series, attribution
    days, n = _scoped_shadow_series(store, strategy_id)
    resp = {'as_of': _now(), 'days_of_data': n, 'min_days': settings.evolve_min_days, 'applied': False, 'count': 0, 'actions': [], 'per_strategy': [], 'last_applied_at': _last_applied_at(store, strategy_id)}
    if n < settings.evolve_min_days:
        resp['status'] = 'waiting_data'
        resp['data_note'] = f'影子净值仅 {n} 日，需累积至 {settings.evolve_min_days} 日才执行升降级/变异；当前可先看 /evolution/attribution 归因报告'
        return resp
    resp['status'] = 'ready'
    per_strategy, actions = _per_strategy_decisions(store, attribution(store, strategy_id), strategy_id)
    resp['count'] = len(actions)
    resp['actions'] = actions
    resp['per_strategy'] = per_strategy
    return resp

def _apply_preview(store: JsonStore, preview_token: str | None, strategy_id: str | None) -> dict:
    from .evolution_01 import _current_preview_key, _now, _preview_scope, _public_preview, _record_scope, _record_source_version
    from .evolution_02 import _strategy_record
    from .evolution_05 import _apply_action
    if not isinstance(preview_token, str) or not preview_token:
        raise EvolutionPreviewConflict('确认应用必须携带预览令牌，请先重新生成预案')
    with _EVOLUTION_LOCK:
        if strategy_id is not None:
            _strategy_record(store, strategy_id)
        record = store.get(_PREVIEW_COLLECTION, preview_token)
        if not isinstance(record, dict):
            raise EvolutionPreviewConflict('预案不存在，请重新生成')
        if _record_scope(record) != _preview_scope(strategy_id):
            raise EvolutionPreviewConflict('预案作用域与本次请求不一致，请重新生成')
        preview_status = record.get('preview_status')
        if preview_status != 'pending':
            raise EvolutionPreviewConflict(f"预案已{preview_status or '失效'}，不能重复提交")
        current_key = _current_preview_key(strategy_id)
        current = store.get(_PREVIEW_COLLECTION, current_key)
        if strategy_id is None and (not isinstance(current, str)):
            current = store.get(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)
        if current != preview_token:
            raise EvolutionPreviewConflict('已生成更新的预案，请确认最新预案')
        if time.time() > float(record.get('_expires_at_epoch') or 0):
            store.update(_PREVIEW_COLLECTION, preview_token, preview_status='expired')
            raise EvolutionPreviewConflict('预案已过期，请重新生成')
        if record.get('state_version') != _record_source_version(store, record, strategy_id):
            raise EvolutionPreviewConflict('策略或影子证据已变化，未应用旧预案；请重新生成')
        actions = record.get('actions') or []
        if record.get('status') != 'ready' or not actions:
            raise EvolutionPreviewConflict('预案没有可应用的进化动作，请重新生成')
        store.update(_PREVIEW_COLLECTION, preview_token, preview_status='applying')
        try:
            for action in actions:
                _apply_action(store, action)
        except Exception:
            store.update(_PREVIEW_COLLECTION, preview_token, preview_status='failed')
            raise
        applied_at = _now()
        store.update(_PREVIEW_COLLECTION, preview_token, preview_status='applied', applied=True, applied_at=applied_at)
        store.delete(_PREVIEW_COLLECTION, current_key)
        if strategy_id is None:
            store.delete(_PREVIEW_COLLECTION, _CURRENT_PREVIEW_KEY)
        return {**_public_preview(record), 'preview_status': 'applied', 'applied': True, 'applied_at': applied_at}
