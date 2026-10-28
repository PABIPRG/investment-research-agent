# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧策略确定性算法迁入；来源与改造见 provenance.json。"""
from __future__ import annotations
from .governance_shared import __all__, genome

def niche_key(kind: str, *, event_type=None, direction=None) -> str:
    """生态位指纹：因子族 × 事件池 × 方向。

    kind 归入其生态位族（genome.family_of），单例 kind 就用自身；同一族内换 kind(P2)
    视为同一生态位候选，不因换了个同族打法就绕过去重。
    """
    fam = genome.family_of(str(kind or '')) or str(kind or '')
    return '|'.join((str(fam), str(event_type or ''), str(direction or '')))

def pearson(xs, ys):
    """Pearson 相关系数。len<2 或某列零方差 → None。纯实现，无 numpy 依赖。"""
    if xs is None or ys is None or len(xs) != len(ys) or (len(xs) < 2):
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum(((x - mx) * (y - my) for x, y in zip(xs, ys)))
    vx = sum(((x - mx) ** 2 for x in xs))
    vy = sum(((y - my) ** 2 for y in ys))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy) ** 0.5

def shadow_correlation(a, b) -> float | None:
    """两条影子净值序列（dict[date,nav]）的相关系数，日期交集按序对齐。"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    return pearson([a[d] for d in common], [b[d] for d in common])

def is_better(candidate_nav, incumbent_nav) -> bool:
    """候选是否严格优于在位的同生态位策略。"""
    try:
        return float(candidate_nav) > float(incumbent_nav)
    except (TypeError, ValueError):
        return False

def clone_blocked(corr, corr_max: float, candidate_better: bool) -> bool:
    """同生态位克隆去重裁决：高相关(corr≥corr_max) 且更差 → 拒绝入池。

    corr=None（样本不足）或未过阈值 → 不拦。
    """
    if corr is None:
        return False
    if corr_max is None:
        return False
    if float(corr) < float(corr_max):
        return False
    return not candidate_better

def stagnant(nav_series, *, stale_days: int) -> bool:
    """停滞判定：连续 stale_days 天未刷新影子净值新高。

    把「历史已达顶」当作对照基线：若最近一个滑窗内再也追不上滑窗之前的历史新高
    （即窗口内最大净值 ≤ 窗口前历史最大净值），说明长期横/阴、不创新高 → 停滞。
    nav_series: 按日期升序的 dict[date, nav]。
    样本不足（总长 ≤ stale_days）无法判断 → False（保守）。
    """
    if not isinstance(nav_series, dict) or stale_days is None or int(stale_days) <= 0:
        return False
    series = [(d, v) for d, v in nav_series.items() if v is not None and _num(v) is not None]
    series.sort(key=lambda dv: dv[0])
    n = int(stale_days)
    if len(series) <= n:
        return False
    vals = [float(v) for _, v in series]
    window = vals[-n:]
    prior_peak = max(vals[:-n])
    return max(window) <= prior_peak

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
