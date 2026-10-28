# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .strategies_shared import Callable, JsonStore, KINDS, VERIFICATION_STATUSES, _ALLOWED_PREFIXES, _DEFAULT_PARAMS, _EVENTS_CACHE, _EVENTS_CACHE_LOCK, _EVENTS_CLOCK, _EVENTS_FAILURE, _EVENTS_REFRESH_LOCK, _LONLY, date, hashlib, json, logging, math, re, settings, threading, time, timedelta, uuid

def _str2md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:10]

def _verification_outcome(out_summary: dict, min_oos: int) -> tuple[str, bool, str]:
    """把样本外指标转成验证分类、阈值布尔值和可审计原因。"""
    oos_n = int(out_summary.get('n_evaluated') or 0)
    oos_wr = out_summary.get('win_rate_pct')
    oos_avg = out_summary.get('avg_simulated_return_pct')
    if oos_n < min_oos:
        return ('insufficient', False, f'样本外成交不足({oos_n}<{min_oos})')
    if oos_wr is not None and oos_avg is not None and (oos_wr >= 50.0) and (oos_avg > 0):
        return ('passed', True, '样本外胜率/均收益达标')
    return ('not_passed', False, f'样本外未达标(wr={oos_wr}, avg={oos_avg})')

def _ma(close, n: int):
    """n 日均线；min_periods=n 保证前 n 根为 NaN（warmup 期不误触发）。"""
    return close.rolling(n, min_periods=n).mean()

def _rsi(close, n: int=14):
    """Wilder RSI。avg_loss==0（一路涨）填 100，避免除零产生 NaN 误触发买入。"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, float('nan'))
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.where(avg_loss.notna() & avg_loss.ne(0), 100.0)

def _make_df(hist: list[dict]):
    """[{"date","open","high","low","close"}] → 按 date 升序 DataFrame，剔除 close NaN 行。"""
    import pandas as pd
    df = pd.DataFrame(hist)
    df = df.dropna(subset=['close'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def signal_series(df, kind: str, params: dict):
    """返回与 df 等长的 0/1 序列（1=持多）。只用 ≤t 数据（因果）。
    warmup 期（指标 NaN）一律 0，不产生伪穿越。"""
    import pandas as pd
    if kind == 'ma_cross':
        fast, slow = (int(params.get('fast', 5)), int(params.get('slow', 20)))
        if fast >= slow:
            raise ValueError(f'ma_cross fast({fast}) 必须小于 slow({slow})')
        ma_f = _ma(df['close'], fast)
        ma_s = _ma(df['close'], slow)
        sig = (ma_f > ma_s).astype(int).where(ma_f.notna() & ma_s.notna(), 0)
        return sig.fillna(0).astype(int)
    if kind == 'rsi_reversal':
        n = int(params.get('n', 14))
        lo, hi = (float(params.get('oversold', 30)), float(params.get('overbought', 70)))
        rsi = _rsi(df['close'], n)
        raw = pd.Series(0, index=df.index, dtype=float)
        raw[rsi < lo] = 1.0
        raw[rsi > hi] = 0.0
        sig = raw.where(rsi.notna(), 0.0).ffill().fillna(0.0)
        return sig.astype(int)
    if kind == 'breakout':
        n = int(params.get('n', 20))
        up = df['high'].rolling(n).max().shift(1)
        dn = df['low'].rolling(n).min().shift(1)
        raw = pd.Series(float('nan'), index=df.index, dtype=float)
        raw[df['close'] > up] = 1.0
        raw[df['close'] < dn] = 0.0
        return raw.ffill().fillna(0.0).astype(int)
    if kind == 'bollinger':
        n = int(params.get('n', 20))
        k = float(params.get('k', 2.0))
        ma = _ma(df['close'], n)
        sd = df['close'].rolling(n, min_periods=n).std()
        lower = ma - k * sd
        raw = pd.Series(float('nan'), index=df.index, dtype=float)
        raw[df['close'] < lower] = 1.0
        raw[df['close'] > ma] = 0.0
        return raw.ffill().fillna(0.0).astype(int)
    if kind == 'volume_breakout':
        n = int(params.get('n', 20))
        mult = float(params.get('vol_mult', 1.5))
        up = df['high'].rolling(n).max().shift(1)
        dn = df['low'].rolling(n).min().shift(1)
        vol = pd.to_numeric(df['volume'], errors='coerce').fillna(0.0) if 'volume' in df.columns else pd.Series(0.0, index=df.index)
        vol_ma = vol.rolling(n, min_periods=n).mean().shift(1)
        breakout = (df['close'] > up) & (vol > mult * vol_ma)
        raw = pd.Series(float('nan'), index=df.index, dtype=float)
        raw[breakout] = 1.0
        raw[df['close'] < dn] = 0.0
        return raw.ffill().fillna(0.0).astype(int)
    n = int(params.get('n', 10))
    return (df['close'] > df['close'].shift(n)).fillna(0).astype(int)

def _px(df, i: int) -> float:
    """第 i 根 bar 成交价：开盘优先，开盘 NaN（停牌）用收盘兜底。"""
    op = df['open'].iloc[i]
    if pd_notna(op):
        return float(op)
    return float(df['close'].iloc[i])

def pd_notna(v) -> bool:
    import math
    if v is None:
        return False
    try:
        return not math.isnan(float(v))
    except (TypeError, ValueError):
        return True

def simulate_trades(df, sig, lot_size: int=100) -> list[dict]:
    """单标的逐 bar 状态机 → 已平仓成交列表。序列末尾仍持仓→最后收盘强平。
    返回每条 {ticker, entry_date, entry_price, exit_date, exit_price, bars_held,
    direction, ret_pct, exit_reason}。"""
    n = len(df)
    trades: list[dict] = []
    open_trade: dict | None = None
    prev = 0
    for t in range(n):
        cur = int(sig.iloc[t]) if pd_notna(sig.iloc[t]) else 0
        if open_trade is None and prev == 0 and (cur == 1):
            if t + 1 < n:
                open_trade = {'ticker': '', 'entry_date': df['date'].iloc[t + 1], 'entry_price': _px(df, t + 1)}
        elif open_trade is not None and prev == 1 and (cur == 0):
            if t + 1 < n:
                trades.append(_close_trade(open_trade, df, t + 1, 'signal'))
                open_trade = None
        prev = cur
    if open_trade is not None:
        trades.append(_close_trade(open_trade, df, n - 1, 'series_end', use_close=True))
    return trades

def _close_trade(open_trade: dict, df, i: int, reason: str, use_close: bool=False) -> dict:
    entry = float(open_trade['entry_price'])
    exit_px = float(df['close'].iloc[i]) if use_close else _px(df, i)
    ret = (exit_px - entry) / entry * 100.0 if entry else 0.0
    return {'ticker': open_trade.get('ticker', ''), 'entry_date': open_trade['entry_date'], 'entry_price': entry, 'exit_date': df['date'].iloc[i], 'exit_price': exit_px, 'bars_held': max(i - _date_index_open(df, open_trade['entry_date']), 1), 'direction': 'long', 'ret_pct': round(ret, 4), 'exit_reason': reason}

def _date_index_open(df, entry_date: str) -> int:
    """open_trade 记录的是 t+1 的成交行；回退到开仓意图所在行以算持仓天数。"""
    idx = df.index[df['date'] == entry_date]
    if len(idx):
        return int(idx[0]) - 1
    return 0

def trades_to_decision_rows(trades: list[dict], ticker: str, direction: str, neutral_band_pct: float=2.0) -> list[dict]:
    """把 simulate_trades 输出包装成 backtest_engine.compute_summary 认识的条目。
    字段语义：eval_status="evaluated"（否则算 insufficient）；hit_sl/hit_tp=None
    （规则回测不设止损止盈，正确排除触发率）；direction 只做方向映射，系统 long-only。"""
    from .backtest_engine import classify_outcome
    rows = []
    for tr in trades:
        ret = float(tr['ret_pct'])
        outcome, dir_correct = classify_outcome(ret, 'up', neutral_band_pct)
        rows.append({'eval_status': 'evaluated', 'key': f"{ticker}_{tr['entry_date']}", 'ticker': ticker, 'trade_date': tr['entry_date'], 'action': '买入', 'direction_expected': 'up', 'position_recommendation': 'long', 'outcome': outcome, 'direction_correct': dir_correct, 'simulated_return_pct': ret, 'stock_return_pct': ret, 'hit_sl': None, 'hit_tp': None, 'first_hit': 'not_applicable', 'first_hit_days': None, 'exit_reason': tr['exit_reason'], 'exit_price': tr['exit_price'], 'end_bar_date': tr['exit_date'], 'n_forward_bars': tr['bars_held']})
    return rows
