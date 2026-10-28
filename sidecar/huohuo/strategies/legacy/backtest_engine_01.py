# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .backtest_engine_shared import ACTION_DIRECTION, Any, BEARISH_KEYWORDS, BULLISH_KEYWORDS, HOLD_KEYWORDS, NEGATION_CONNECTOR_WORDS, NEGATION_PATTERNS, Optional, WAIT_KEYWORDS, _PRICE_PATTERNS, math, re

def classify_outcome(stock_return_pct: Optional[float], direction_expected: str, neutral_band_pct: float=2.0) -> tuple[Optional[str], Optional[bool]]:
    """(outcome win/loss/neutral, direction_correct True/False/None)。"""
    if stock_return_pct is None:
        return (None, None)
    band = abs(float(neutral_band_pct))
    r = float(stock_return_pct)
    if direction_expected == 'up':
        if r >= band:
            return ('win', True)
        if r <= -band:
            return ('loss', False)
        return ('neutral', None)
    if direction_expected == 'down':
        if r <= -band:
            return ('win', True)
        if r >= band:
            return ('loss', False)
        return ('neutral', None)
    if direction_expected == 'not_down':
        if r >= 0:
            return ('win', True)
        if r <= -band:
            return ('loss', False)
        return ('neutral', None)
    if abs(r) <= band:
        return ('win', True)
    return ('loss', False)

def _avg(values: list[Optional[float]]) -> Optional[float]:
    items = [float(v) for v in values if v is not None]
    if not items:
        return None
    return round(sum(items) / len(items), 4)

def _sample_std(values: list[float]) -> Optional[float]:
    """样本标准差（numpy 无关，聚合条目少）。"""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum(((v - mean) ** 2 for v in values)) / (n - 1)
    return math.sqrt(var) if var > 0 else None

def _annualized_sharpe(sim_rets_pct: list[float]) -> Optional[float]:
    """年化 Sharpe：mean/sample_std * sqrt(252)。<2 笔或 std<=0 → None。"""
    if len(sim_rets_pct) < 2:
        return None
    std = _sample_std(sim_rets_pct)
    if std is None or std <= 0:
        return None
    mean = sum(sim_rets_pct) / len(sim_rets_pct)
    return round(mean / std * math.sqrt(252), 4)

def _max_drawdown_pct(sim_rets_pct: list[float]) -> float:
    """逐笔收益序列的峰谷最大回撤（负 %）；空序列 → 0.0。"""
    if not sim_rets_pct:
        return 0.0
    peak = 1.0
    max_dd = 0.0
    equity = 1.0
    for r in sim_rets_pct:
        equity *= 1 + r / 100
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return round(max_dd * 100, 4)

def compute_summary(results: list[dict], **ctx: Any) -> dict:
    """聚合回测结果：方向准确率/胜率/平均收益/止损止盈/Sharpe/回撤。

    ctx 透传上下文（engine_version / eval_window_days / min_age_days /
    n_decisions_total / n_candidates_evaluated）。results 含 evaluated 与
    insufficient_data 两类条目。
    """
    completed = [r for r in results if (r.get('eval_status') or '') == 'evaluated']
    insufficient_count = sum((1 for r in results if (r.get('eval_status') or '') == 'insufficient_data'))
    fetch_failed_count = sum((1 for r in results if (r.get('eval_status') or '') == 'fetch_failed'))
    win_count = sum((1 for r in completed if r.get('outcome') == 'win'))
    loss_count = sum((1 for r in completed if r.get('outcome') == 'loss'))
    neutral_count = sum((1 for r in completed if r.get('outcome') == 'neutral'))
    dir_denom = sum((1 for r in completed if r.get('direction_correct') is not None))
    dir_num = sum((1 for r in completed if r.get('direction_correct') is True))
    long_count = sum((1 for r in completed if r.get('position_recommendation') == 'long'))
    cash_count = len(completed) - long_count
    sim_rets = [float(r['simulated_return_pct']) for r in completed if r.get('simulated_return_pct') is not None]
    stop_applicable = [r for r in completed if r.get('hit_sl') is not None]
    tp_applicable = [r for r in completed if r.get('hit_tp') is not None]
    target_applicable = [r for r in completed if r.get('hit_sl') is not None or r.get('hit_tp') is not None]
    hit_days = [float(r['first_hit_days']) for r in target_applicable if r.get('first_hit_days') is not None and r.get('first_hit') in ('stop_loss', 'take_profit', 'ambiguous')]
    breakdown = _advice_breakdown(completed)
    diagnostics = {'eval_status': _count_by(results, 'eval_status'), 'first_hit': _count_by(completed, 'first_hit')}
    return {'engine_version': ctx.get('engine_version', 'v1'), 'eval_window_days': int(ctx.get('eval_window_days', 10)), 'min_age_days': ctx.get('min_age_days'), 'n_decisions_total': int(ctx.get('n_decisions_total', len(results))), 'n_candidates_evaluated': int(ctx.get('n_candidates_evaluated', 0)), 'n_evaluated': len(completed), 'n_insufficient_data': insufficient_count, 'n_fetch_failed': fetch_failed_count, 'long_count': long_count, 'cash_count': cash_count, 'win_count': win_count, 'loss_count': loss_count, 'neutral_count': neutral_count, 'direction_accuracy_pct': round(dir_num / dir_denom * 100, 2) if dir_denom else None, 'win_rate_pct': round(win_count / (win_count + loss_count) * 100, 2) if win_count + loss_count else None, 'avg_stock_return_pct': _avg([r.get('stock_return_pct') for r in completed]), 'avg_simulated_return_pct': _avg(sim_rets), 'sharpe_annualized': _annualized_sharpe(sim_rets), 'max_drawdown_pct': _max_drawdown_pct(sim_rets), 'stop_loss_trigger_rate': round(sum((1 for r in stop_applicable if r.get('hit_sl') is True)) / len(stop_applicable) * 100, 2) if stop_applicable else None, 'take_profit_trigger_rate': round(sum((1 for r in tp_applicable if r.get('hit_tp') is True)) / len(tp_applicable) * 100, 2) if tp_applicable else None, 'ambiguous_rate': round(sum((1 for r in target_applicable if r.get('first_hit') == 'ambiguous')) / len(target_applicable) * 100, 2) if target_applicable else None, 'avg_days_to_first_hit': _avg(hit_days), 'advice_breakdown': breakdown, 'diagnostics': diagnostics}

def _advice_breakdown(completed: list[dict]) -> dict:
    breakdown: dict[str, dict] = {}
    for row in completed:
        advice = str(row.get('action') or '未知')
        bucket = breakdown.setdefault(advice, {'total': 0, 'win': 0, 'loss': 0, 'neutral': 0, 'win_rate_pct': None})
        bucket['total'] += 1
        outcome = row.get('outcome')
        if outcome in ('win', 'loss', 'neutral'):
            bucket[outcome] += 1
    for bucket in breakdown.values():
        denom = bucket['win'] + bucket['loss']
        bucket['win_rate_pct'] = round(bucket['win'] / denom * 100, 2) if denom else None
    return breakdown

def _count_by(items: list[dict], field: str) -> dict:
    counts: dict[str, int] = {}
    for row in items:
        key = str(row.get(field) or 'unknown')
        counts[key] = counts.get(key, 0) + 1
    return counts
