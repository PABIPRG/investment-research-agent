# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .shadow_shared import JsonStore, _HIST_LOOKBACK_DAYS, _make_df, date, json, logging, pd_notna, settings, signal_series, time, timedelta, uuid

def _replay_pos(df_track, sig_track, capital: float, symbol: str) -> dict:
    """track_from 起的单一路径重放 → 当前持仓状态 + 平仓记录。

    状态机：bar t 信号（收盘后意图）→ bar t+1 开盘成交。t=0 无条件（track_from 首日不建仓）。
    开盘缺失（停牌）用收盘兜底，与回测 _px 一致。
    返回 {qty, entry_price, entry_date, avg_cost, cash, last_close, equity, signal_intent, closed}。
    """
    n = len(df_track)
    qty, cash = (0.0, float(capital))
    entry_price = entry_date = avg_cost = None
    closed: list[dict] = []
    prev_intent = 0
    for t in range(n):
        row = df_track.iloc[t]
        d = str(row['date'])
        if t > 0:
            op = row['open']
            if not pd_notna(op):
                op = row['close']
            op = float(op)
            if prev_intent == 1 and qty == 0 and (op > 0):
                qty = cash / op
                cash = 0.0
                entry_price = avg_cost = op
                entry_date = d
            elif prev_intent == 0 and qty > 0 and (op > 0):
                proceeds = qty * op
                cash = proceeds
                closed.append({'symbol': symbol, 'entry_date': entry_date, 'exit_date': d, 'entry_price': round(entry_price, 4), 'exit_price': round(op, 4), 'ret_pct': round((op - entry_price) / entry_price * 100.0, 4) if entry_price else 0.0})
                qty, entry_price, entry_date, avg_cost = (0.0, None, None, None)
        prev_intent = int(sig_track.iloc[t]) if pd_notna(sig_track.iloc[t]) else 0
    last_close = float(df_track['close'].iloc[-1]) if n else None
    equity = cash + (qty * last_close if last_close else 0.0)
    return {'qty': round(qty, 4), 'entry_price': entry_price, 'entry_date': entry_date, 'avg_cost': avg_cost, 'cash': round(cash, 4), 'last_close': last_close, 'equity': round(equity, 4), 'signal_intent': int(prev_intent), 'closed': closed}

def _closed_trade_identity(trade: dict) -> tuple:
    """同一历史重放的平仓身份；旧记录缺关键日期时退化为完整内容。"""
    symbol = trade.get('symbol')
    entry_date = trade.get('entry_date')
    exit_date = trade.get('exit_date')
    if symbol and entry_date and exit_date:
        return ('closed', str(symbol), str(entry_date), str(exit_date))
    return ('legacy', json.dumps(trade, ensure_ascii=False, sort_keys=True, default=str))

def _merge_closed_trades(fresh: list[dict], current: object) -> list[dict]:
    """新鲜重放优先覆盖同身份旧记录，并保留本次未重放到的历史成交。"""
    merged: list[dict] = []
    seen: set[tuple] = set()
    existing = current if isinstance(current, list) else []
    for trade in [*fresh, *existing]:
        if not isinstance(trade, dict):
            continue
        identity = _closed_trade_identity(trade)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(trade)
    return merged[:200]

def _regime_hibernation(strategies: list[dict], store: JsonStore, trade_date: str) -> tuple[list[dict], set[str]]:
    """P5 冬眠门控（纯过滤，默认关 → 原样返回）：把「当日 regime 不在 gate.allow」的策略
    从本次触发里剔除并记录为冬眠。regime unknown/无 regime/门控关 → 全放行（conservative）。
    返回 (保留列表, 冬眠 sid 集合)。"""
    if not getattr(settings, 'evolve_hibernate_enabled', False) or not strategies:
        return (list(strategies), set())
    from . import genome as _gm
    from . import regime as _rg
    cur = _rg.latest_regime(store, as_of_date=trade_date)
    regime = (cur or {}).get('regime') if isinstance(cur, dict) else None
    if not regime or regime == 'unknown':
        return (list(strategies), set())
    kept: list[dict] = []
    hibernated: set[str] = set()
    for s in strategies:
        allow = ((_gm.read_gene(s) or {}).get('regime_gate') or {}).get('allow') or []
        if regime in allow:
            kept.append(s)
        else:
            hibernated.add(str(s.get('id')))
    return (kept, hibernated)

def _snapshot(r: dict) -> dict:
    return {'name': r.get('name'), 'kind': r.get('kind'), 'symbols': r.get('symbols'), 'initial_capital': r.get('initial_capital'), 'equity': r.get('equity'), 'nav': r.get('nav'), 'track_from': r.get('track_from'), 'closed_count': r.get('closed_count', 0), 'per_symbol': r.get('per_symbol'), 'symbol_errors': r.get('symbol_errors')}

def _overall_nav(results: dict) -> float | None:
    if not results:
        return None
    tot_cap = sum((r['initial_capital'] for r in results.values()))
    tot_equity = sum((r['equity'] for r in results.values()))
    if not tot_cap:
        return None
    return round(tot_equity / tot_cap, 6)
