# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .fitness_shared import VERDICTS, _BASIS_INSUFFICIENT, _BASIS_NOT_RUN, __all__

def nav_verdict(nav: float | None, *, promote_nav: float, demote_nav: float, retire_nav: float) -> str:
    """绝对净值三线原始判定（复刻 v1：retire 优先，其次 demote，其次 promote）。"""
    if nav is None:
        return 'hold'
    if nav <= retire_nav:
        return 'retire'
    if nav <= demote_nav:
        return 'demote'
    if nav >= promote_nav:
        return 'promote'
    return 'hold'

def percentile(nav: float | None, peer_navs: list[float]) -> float | None:
    """nav 在同批 peer 终值中的分位（0~100），含自身；并列取中位。peer 不足返回 None。"""
    if nav is None or not peer_navs:
        return None
    vals = [float(x) for x in peer_navs if x is not None]
    if not vals:
        return None
    target = float(nav)
    below = sum((1 for v in vals if v < target))
    equal = sum((1 for v in vals if v == target))
    return round(100.0 * (below + 0.5 * equal) / len(vals), 1)

def overfit_of(extended: dict | None, *, gap_pct: float, min_trades: int) -> dict:
    """从 extended_backtest（P0.4）判过拟合。

    输入 per_symbol 明细不可用时（None/空/无字段）→ flag=False、basis=not_run，不介入。
    需 OOS 样本 ≥ min_trades 才下结论（样本太少无从判过拟合，不算 flag）。
    判据：IS 胜率 − OOS 胜率 ≥ gap_pct（用各符号样本数加权不太现实，简化为池内平均胜率差，
    由调用侧按池聚合后传入 per_symbol 或以聚合字段传入）。
    """
    if not isinstance(extended, dict):
        return {'flag': False, 'basis': _BASIS_NOT_RUN, 'gap_pct': None, 'oos_trades': 0}
    per = extended.get('per_symbol')
    if not isinstance(per, dict) or not per:
        return {'flag': False, 'basis': _BASIS_NOT_RUN, 'gap_pct': None, 'oos_trades': 0}
    is_wr: list[float] = []
    oos_wr: list[float] = []
    oos_trades = 0
    for sym, st in per.items():
        if not isinstance(st, dict):
            continue
        iw = st.get('in_winrate_pct')
        ow = st.get('out_winrate_pct')
        if iw is None or ow is None:
            continue
        is_wr.append(float(iw))
        oos_wr.append(float(ow))
        oos_trades += int(st.get('out_trades') or 0)
    if not oos_wr or oos_trades < max(1, min_trades):
        return {'flag': False, 'basis': _BASIS_INSUFFICIENT, 'gap_pct': None, 'oos_trades': oos_trades}
    gap = sum(is_wr) / len(is_wr) - sum(oos_wr) / len(oos_wr)
    return {'flag': bool(gap >= gap_pct), 'basis': 'flag' if gap >= gap_pct else 'ok', 'gap_pct': round(gap, 1), 'oos_trades': oos_trades}

def effective_lines(*, nav: float | None, peer_navs: list[float] | None, mode: str, min_peers: int, promote_nav: float, demote_nav: float, retire_nav: float, promote_percentile: float, retire_percentile: float) -> dict:
    """按 mode + relative 分位返回「生效净值三线」与分组信息。

    返回 {promote_nav, demote_nav, retire_nav, percentile, rank, gated}：
      - mode 非 relative/excess，或 peers 不足 → 原样三线（=v1），percentile=None。
      - 高位组：demote/retire 线压到 -∞（绝不因绝对净值误杀抗跌 alpha）。
      - 非高位组：promote 线拉到 +∞（绝不因过线就升级跟风 beta）。
      gated ∈ {"none","rescue_top","block_promote"} 说明本次是否被分组改写。
    """
    res = {'promote_nav': promote_nav, 'demote_nav': demote_nav, 'retire_nav': retire_nav, 'percentile': None, 'rank': 'unranked', 'gated': 'none'}
    if nav is None or mode not in ('relative', 'excess'):
        return res
    peers = [float(x) for x in peer_navs if x is not None] if peer_navs else []
    if len(peers) < min_peers:
        return res
    p = percentile(nav, peers)
    if p is None:
        return res
    res['percentile'] = p
    if p >= promote_percentile:
        res['rank'] = 'top'
        res['demote_nav'] = float('-inf')
        res['retire_nav'] = float('-inf')
        res['gated'] = 'rescue_top'
    elif p <= retire_percentile:
        res['rank'] = 'bottom'
        res['promote_nav'] = float('inf')
        res['gated'] = 'block_promote'
    else:
        res['rank'] = 'mid'
        res['promote_nav'] = float('inf')
        res['gated'] = 'block_promote'
    return res

def _fused_verdict(*, nav_eff: dict, overfit: dict, mode: str, bench_return_pct: float | None, excess_min: float) -> tuple[str, str]:
    """在生效线 + overfit + excess 之上给最终裁定。返回 (decision, blocked_by)。

    blocked_by ∈ {"none","overfit","rank","excess"} 说明是谁把 v1 的绝对线裁定压了回去。
    """
    nav = nav_eff.get('_nav')
    abs_eff = nav_verdict(nav, promote_nav=nav_eff['promote_nav'], demote_nav=nav_eff['demote_nav'], retire_nav=nav_eff['retire_nav'])
    if overfit.get('flag'):
        return ('hold', 'overfit') if abs_eff == 'promote' else (abs_eff, 'none')
    if mode == 'excess' and abs_eff == 'promote':
        if bench_return_pct is not None:
            excess = (nav - 1.0) * 100.0 - bench_return_pct
            if excess <= excess_min:
                return ('hold', 'excess')
    return (abs_eff, 'none' if nav_eff.get('gated') == 'none' else 'rank')

def compute_profile(*, nav: float | None, peer_navs: list[float] | None=None, mode: str='log', min_peers: int=3, promote_nav: float, demote_nav: float, retire_nav: float, promote_percentile: float=80.0, retire_percentile: float=20.0, extended: dict | None=None, overfit_gap_pct: float=25.0, overfit_min_trades: int=4, bench_return_pct: float | None=None, excess_min: float=0.0) -> dict:
    """一条策略的多维适应度画像 + 最终裁定。

    输入均显式传标量/序列（纯函数），供 evolution 在判定循环内逐策略调用，
    也便于单测用合成 peer/bench/extended 直接喂。
    """
    abs_verdict = nav_verdict(nav, promote_nav=promote_nav, demote_nav=demote_nav, retire_nav=retire_nav)
    ov = overfit_of(extended, gap_pct=overfit_gap_pct, min_trades=overfit_min_trades)
    eff = effective_lines(nav=nav, peer_navs=peer_navs, mode=mode, min_peers=min_peers, promote_nav=promote_nav, demote_nav=demote_nav, retire_nav=retire_nav, promote_percentile=promote_percentile, retire_percentile=retire_percentile)
    eff = {**eff, '_nav': nav}
    decision, blocked_by = _fused_verdict(nav_eff=eff, overfit=ov, mode=mode, bench_return_pct=bench_return_pct, excess_min=excess_min)
    excess_info = {'bench_return_pct': bench_return_pct}
    if nav is not None and bench_return_pct is not None:
        excess_info['excess_pct'] = round((nav - 1.0) * 100.0 - bench_return_pct, 3)
    else:
        excess_info['excess_pct'] = None
    return {'mode': mode, 'nav': nav, 'percentile': eff.get('percentile'), 'rank': eff.get('rank'), 'absolute': {'verdict': abs_verdict, 'promote_nav': promote_nav, 'demote_nav': demote_nav, 'retire_nav': retire_nav}, 'relative': {'percentile': eff.get('percentile'), 'rank': eff.get('rank'), 'min_peers': min_peers}, 'excess': excess_info, 'overfit': ov, 'decision': decision, 'blocked_by': blocked_by, 'gated': eff.get('gated')}
