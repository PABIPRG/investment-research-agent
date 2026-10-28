# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .regime_shared import Iterable, JsonStore, Optional, Sequence, _INDEX_COLLECTION, _LATEST_KEY, _REGIME_COLLECTION, __all__, deque, time

def _now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')

def _std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    var = sum(((x - m) ** 2 for x in xs)) / len(xs)
    return var ** 0.5

def _rolling_std(xs: Sequence[float], window: int) -> list[float]:
    out: list[float] = []
    dq: deque = deque()
    s = 0.0
    s2 = 0.0
    for v in xs:
        dq.append(v)
        s += v
        s2 += v * v
        if len(dq) > window:
            old = dq.popleft()
            s -= old
            s2 -= old * old
        if len(dq) == window:
            m = s / window
            var = s2 / window - m * m
            out.append((var if var > 0 else 0.0) ** 0.5)
    return out

def _daily_returns(closes: Sequence[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]

def classify_regime(closes: Sequence[float], *, ma_fast: int=20, ma_slow: int=60, vol_window: int=20, high_vol_ratio: float=1.5, trend_dist_pct: float=0.02, slope_ref_days: int=5) -> dict:
    """从升序日 close 序列判 regime。纯函数。

    需足够历史（≥ max(ma_slow, 2*ma_fast) + slope_ref_days + 1），否则返回 unknown。
    返回字典字段见函数内注释，供落库与单测断言。
    """
    closes = [float(x) for x in closes]
    n = len(closes)
    base = {'regime': 'unknown', 'underlying': None, 'confidence_pct': None, 'vol_annualized_pct': None, 'dist_slow_pct': None, 'ma_fast_slope_pct': None, 'needs_more_data': True, 'samples': n}
    need = max(ma_slow, ma_fast * 2) + slope_ref_days + 1
    if n < need:
        return base
    ma_slow_now = sum(closes[-ma_slow:]) / ma_slow
    ma_slow_prev = sum(closes[-ma_slow - slope_ref_days:-slope_ref_days]) / ma_slow
    ma_fast_now = sum(closes[-ma_fast:]) / ma_fast
    ma_fast_prev = sum(closes[-ma_fast - slope_ref_days:-slope_ref_days]) / ma_fast
    close_now = closes[-1]
    dist_slow = close_now / ma_slow_now - 1.0 if ma_slow_now else 0.0
    slope_fast = ma_fast_now / ma_fast_prev - 1.0 if ma_fast_prev else 0.0
    rets = _daily_returns(closes)
    vol_now = _std(rets[-vol_window:]) * 252 ** 0.5 if len(rets) >= vol_window else None
    vol_base = None
    if len(rets) >= vol_window:
        hist = rets[-200:]
        vol_series = [_std(hist[i:i + vol_window]) * 252 ** 0.5 for i in range(0, len(hist) - vol_window + 1)]
        if vol_series:
            vol_series.sort()
            vol_base = vol_series[len(vol_series) // 2]
    high_vol = vol_now is not None and vol_base is not None and (vol_base > 0) and (vol_now > vol_base * high_vol_ratio)
    trend_up = not high_vol and dist_slow >= trend_dist_pct and (slope_fast > 0)
    trend_down = not high_vol and dist_slow <= -trend_dist_pct and (slope_fast < 0)
    underlying = None
    if high_vol:
        regime = 'high_vol'
        underlying = 'trend_up' if dist_slow >= trend_dist_pct and slope_fast > 0 else 'trend_down' if dist_slow <= -trend_dist_pct and slope_fast < 0 else 'oscillation'
    elif trend_up:
        regime = 'trend_up'
        underlying = None
    elif trend_down:
        regime = 'trend_down'
        underlying = None
    else:
        regime = 'oscillation'
        underlying = None
    confidence = 0.0
    if not high_vol:
        magnitude = min(1.0, abs(dist_slow) / (trend_dist_pct * 3 or 1e-09))
        confidence = max(0.0, min(1.0, magnitude))
    else:
        excess = vol_now / vol_base - 1.0 if vol_now and vol_base else 0.0
        confidence = max(0.0, min(1.0, excess / (high_vol_ratio - 1.0 or 1e-09)))
    return {'regime': regime, 'underlying': underlying, 'confidence_pct': round(confidence * 100, 1), 'vol_annualized_pct': round(vol_now * 100, 2) if vol_now is not None else None, 'dist_slow_pct': round(dist_slow * 100, 3), 'ma_fast_slope_pct': round(slope_fast * 100, 3), 'needs_more_data': False, 'samples': n}

def record_index_close(store: JsonStore, code: str, trade_date: str, close: float, name: str | None=None) -> None:
    """把某基准某日收盘 append 进 market_index（幂等覆盖同日）。"""
    if not code or not trade_date:
        return
    close = float(close)
    if close <= 0:
        return

    def transform(current):
        doc = dict(current or {})
        dates = dict(doc.get('dates') or {})
        dates[trade_date] = close
        doc['code'] = code
        doc['name'] = name or doc.get('name') or code
        doc['updated_at'] = _now()
        doc['dates'] = dates
        return doc
    store.mutate(_INDEX_COLLECTION, code, transform)

def _sorted_dates(dates: dict) -> list[str]:
    return sorted((d for d in dates if isinstance(d, str)))

def classify_and_store(store: JsonStore, as_of: str | None=None, *, code: str | None=None, ma_fast: int | None=None, ma_slow: int | None=None, vol_window: int | None=None, high_vol_ratio: float | None=None, trend_dist_pct: float | None=None) -> dict:
    """读 market_index 某基准最近 close 序列，判 regime 并落 market_regime（按日 + _latest 指针）。

    返回落库的判定 dict（无法判定则返回 unknown dict 且不写日记录，仅刷新 _latest 若旧指针为空）。
    """
    from .config import settings
    code = code or settings.regime_index
    doc = store.get(_INDEX_COLLECTION, code) or {}
    dates = dict(doc.get('dates') or {})
    if not dates:
        return {'date': None, 'index_code': code, 'regime': 'unknown', 'confidence_pct': None, 'samples': 0, 'needs_more_data': True}
    ordered = _sorted_dates(dates)
    closes = [float(dates[d]) for d in ordered if float(dates[d]) > 0]
    result = classify_regime(closes, ma_fast=ma_fast if ma_fast is not None else settings.regime_ma_fast, ma_slow=ma_slow if ma_slow is not None else settings.regime_ma_slow, vol_window=vol_window if vol_window is not None else settings.regime_vol_window, high_vol_ratio=high_vol_ratio if high_vol_ratio is not None else settings.regime_high_vol_ratio, trend_dist_pct=trend_dist_pct if trend_dist_pct is not None else settings.regime_trend_dist_pct)
    if result.get('needs_more_data'):
        if store.get(_REGIME_COLLECTION, _LATEST_KEY) is None:
            store.set(_REGIME_COLLECTION, _LATEST_KEY, None)
        return {'date': None, 'index_code': code, 'regime': 'unknown', 'confidence_pct': None, 'samples': result.get('samples'), 'needs_more_data': True}
    as_of = as_of or _now()
    trade_date = ordered[-1]
    record = {'date': trade_date, 'index_code': code, 'regime': result['regime'], 'underlying': result.get('underlying'), 'confidence_pct': result.get('confidence_pct'), 'vol_annualized_pct': result.get('vol_annualized_pct'), 'dist_slow_pct': result.get('dist_slow_pct'), 'ma_fast_slope_pct': result.get('ma_fast_slope_pct'), 'samples': result.get('samples'), 'as_of': as_of}
    store.set(_REGIME_COLLECTION, trade_date, record)
    store.set(_REGIME_COLLECTION, _LATEST_KEY, trade_date)
    return record

def latest_regime(store: JsonStore, as_of_date: str | None=None, *, code: str | None=None) -> dict | None:
    """取最近一个已判定 regime（<= as_of_date 时给当日之前最近档，用于门控）。

    as_of_date 缺省返回全局 _latest；给定时退到 <= 该日的最接近档，避免用未来状态。
    """
    if code is not None:
        pass
    if as_of_date is None:
        latest = store.get(_REGIME_COLLECTION, _LATEST_KEY)
        record = store.get(_REGIME_COLLECTION, latest) if isinstance(latest, str) else None
        return record if isinstance(record, dict) else None
    best = None
    for key, rec in (store.all(_REGIME_COLLECTION) or {}).items():
        if not isinstance(rec, dict) or not isinstance(key, str) or key == _LATEST_KEY:
            continue
        if str(key) <= as_of_date and (best is None or str(key) > best[0]):
            best = (str(key), rec)
    return best[1] if best else None
