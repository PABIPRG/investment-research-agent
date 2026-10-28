# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .strategies_shared import Callable, JsonStore, KINDS, VERIFICATION_STATUSES, _ALLOWED_PREFIXES, _DEFAULT_PARAMS, _EVENTS_CACHE, _EVENTS_CACHE_LOCK, _EVENTS_CLOCK, _EVENTS_FAILURE, _EVENTS_REFRESH_LOCK, _LONLY, date, hashlib, json, logging, math, re, settings, threading, time, timedelta, uuid

def _symbol_equity(df, sig, capital: float) -> list[float]:
    """单标的独立子账户：意图转多→t+1 开盘全仓买入，转空→t+1 开盘清仓。
    返回逐 bar 权益（现金+市值）。"""
    from .strategies_01 import _px, pd_notna
    n = len(df)
    cash = float(capital)
    qty = 0.0
    equity = []
    for t in range(n):
        if t > 0:
            prev_intent = int(sig.iloc[t - 1]) if pd_notna(sig.iloc[t - 1]) else 0
            if prev_intent == 1 and qty == 0:
                px = _px(df, t)
                if px > 0:
                    qty = cash / px
                    cash = 0.0
            elif prev_intent == 0 and qty > 0:
                px = _px(df, t)
                cash = qty * px
                qty = 0.0
        close = float(df['close'].iloc[t])
        equity.append(cash + qty * close)
    return equity

def portfolio_equity_curve(per_symbol: dict, capital_per_symbol: float) -> dict:
    from .strategies import _symbol_equity
    if not per_symbol:
        return {'date': [], 'nav': [], 'daily_return': []}
    series = {s: dict(zip(df['date'].astype(str), _symbol_equity(df, sig, capital_per_symbol))) for s, (df, sig) in per_symbol.items()}
    dates = sorted({d for values in series.values() for d in values})
    last = {s: capital_per_symbol for s in series}
    nav = []
    for day in dates:
        for s, values in series.items():
            if day in values:
                last[s] = values[day]
        nav.append(sum(last.values()) / (len(series) * capital_per_symbol))
    rets = [0.0] + [(nav[i] / nav[i - 1] - 1) * 100 for i in range(1, len(nav))]
    return {'date': dates, 'nav': [round(v, 6) for v in nav], 'daily_return': [round(v, 4) for v in rets]}

def curve_stats(curve: dict) -> dict:
    """组合净值 → 累计收益 / 日频最大回撤 / 年化 Sharpe。"""
    nav = curve.get('nav') or []
    if len(nav) < 2:
        return {'portfolio_return_pct': None, 'portfolio_max_drawdown_pct': None, 'portfolio_sharpe': None}
    ret_pct = (nav[-1] / nav[0] - 1) * 100.0 if nav[0] else None
    peak, max_dd = (nav[0], 0.0)
    for v in nav:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak else 0.0
        max_dd = min(max_dd, dd)
    daily = curve.get('daily_return') or []
    mean = sum(daily) / len(daily) if daily else 0.0
    var = sum(((d - mean) ** 2 for d in daily)) / len(daily) if daily else 0.0
    std = math.sqrt(var)
    sharpe = mean / std * math.sqrt(252) if std > 0 else None
    return {'portfolio_return_pct': round(ret_pct, 4) if ret_pct is not None else None, 'portfolio_max_drawdown_pct': round(max_dd * 100, 4), 'portfolio_sharpe': round(sharpe, 4) if sharpe is not None else None}

def split_in_out(df, sig, oos_frac: float=0.3):
    """先在全序列算 signal（保证 OOS 起点有指标 warmup、不偷看未来），再按行数 70/30 切。
    OOS 独立跑状态机，不继承样本内持仓。"""
    n = len(df)
    split = int(n * (1 - oos_frac))
    split = max(1, min(n - 1, split))
    return (df.iloc[:split].reset_index(drop=True), sig.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True), sig.iloc[split:].reset_index(drop=True))

def _symbol_trade_stats(trades: list[dict]) -> dict:
    """单个标的某侧（样本内/外）已平仓成交的胜负聚合（供归因/overfit）。"""
    if not trades:
        return {'trades': 0, 'wins': 0, 'win_rate_pct': None, 'cum_ret_pct': None}
    wins = sum((1 for t in trades if float(t.get('ret_pct') or 0) > 0))
    cum = sum((float(t.get('ret_pct') or 0) for t in trades))
    return {'trades': len(trades), 'wins': wins, 'win_rate_pct': round(wins / len(trades) * 100, 1), 'cum_ret_pct': round(cum, 2)}

def _trim_curve(curve: dict, keep: int) -> dict:
    """组合净值曲线保留最近 keep 个交易日（date/nav/daily_return 同步截尾）。"""
    nav = curve.get('nav') or []
    n = len(nav)
    if n <= keep:
        return curve
    start = n - keep
    return {key: curve[key][start:] if isinstance(curve.get(key), list) else curve.get(key) for key in ('date', 'nav', 'daily_return')}
