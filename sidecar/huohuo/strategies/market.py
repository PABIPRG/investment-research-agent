"""影子验证与归档召回复用同一基准来源；不依赖此前刚好跑过影子任务。"""
from datetime import date, timedelta
from .history import collect
from .legacy import regime
from .legacy.runtime import settings


def load(service, day):
    try:
        if not hasattr(service.history, 'index'): raise ValueError('没有基准来源')
        start = (date.fromisoformat(day) - timedelta(days=400)).isoformat()
        index, evidence = collect(lambda _, a, b: service.history.index(a, b), '000300', start, day, service.clock)
        if index[-1]['date'] != day: raise ValueError('基准日期落后于当前验证日')
        return {'index': index}, [evidence]
    except Exception:
        return {'regime_note': '本期基准行情不可用，市场环境为未知，不据此召回归档'}, []


def save(docs, day, result):
    index = result.pop('index', None)
    if index:
        for bar in index: regime.record_index_close(docs, settings.regime_index, bar['date'], bar['close'])
        market = regime.classify_and_store(docs, day, code=settings.regime_index,
            ma_fast=settings.regime_ma_fast, ma_slow=settings.regime_ma_slow,
            vol_window=settings.regime_vol_window, high_vol_ratio=settings.regime_high_vol_ratio,
            trend_dist_pct=settings.regime_trend_dist_pct)
        if market.get('regime') not in ('unknown', None): return
    docs.set('market_regime', day, {'date': day, 'regime': None, 'reason': result.get('regime_note', '基准样本不足')})
    docs.set('market_regime', '_latest', day)
