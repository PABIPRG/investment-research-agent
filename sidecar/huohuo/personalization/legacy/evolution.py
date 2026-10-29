# 旧版 outcome 归因纯算法，来源 9c23b1f adapter/evolution.py，原许可见 third-party。
from __future__ import annotations
import time
from .runtime import settings
from .store import JsonStore

def _parse_ts(ts):
    # 使用已有 UTC 规范时间解析，避免本机时区改变兴趣窗口和归因。
    from .local_telemetry import _parse_ts as parse
    value = parse(ts)
    return value.timestamp() if value else None

def _shadow_series(store: JsonStore) -> tuple[list[dict], int]:
    """shadow_equity 按日期升序 → ( [{date, overall_nav, strategies{sid:{nav,…}}}], days )。

    overall_nav 非法/≤0 的日期跳过（幂等跑当日只留一笔）。"""
    eq = store.all("shadow_equity") or {}
    days: list[dict] = []
    for d in sorted(eq.keys()):
        rec = eq[d] or {}
        try:
            ov = float(rec.get("overall_nav") or 0.0)
        except (TypeError, ValueError):
            continue
        if ov > 0:
            days.append(
                {
                    "date": d,
                    "overall_nav": ov,
                    "strategies": rec.get("strategies") or {},
                }
            )
    return days, len(days)

def _per_strategy_series(days: list[dict]) -> dict[str, list[dict]]:
    """每策略影子净值序列 → {sid: [{date, nav}]}（正数只收，非法跳过）。"""
    out: dict[str, list[dict]] = {}
    for d in days:
        for sid, rec in (d.get("strategies") or {}).items():
            try:
                nav = float((rec or {}).get("nav") or 0.0)
            except (TypeError, ValueError):
                continue
            if nav > 0:
                out.setdefault(sid, []).append({"date": d["date"], "nav": nav})
    return out

def decision_outcome(store: JsonStore | None = None) -> dict:
    """R→S→U outcome 归因：用户参与（点击/反馈）或激活的策略 → 影子 outcome。

    - 参与 = 近 N 小时 behavior 里带 strategy_id 的 click/feedback + 所有 active 策略（激活=决策）。
    - 只有「仍在 active」的策略参与计算（watch 算 active，retired 不参与）。
    - delta 是兼容旧消费者的归因强度，不得流入用户风险参数；数据不足（<2 日影子）
      或无样本时 delta=0 + note。
    """
    store = store or JsonStore()
    days, n = _shadow_series(store)
    base = {
        "delta": 0.0,
        "engaged": 0,
        "samples": 0,
        "avg_return_pct": None,
        "note": f"影子净值 {n} 日，不足 2 日不做 outcome 归因",
    }
    if n < 2:
        return base
    engaged: set[str] = set()
    win = time.time() - settings.personalized_behavior_hours * 3600
    for r in store.get("behavior", "default") or []:
        if not isinstance(r, dict):
            continue
        ts = _parse_ts(r.get("ts") or r.get("server_ts"))
        if ts is None or ts < win:
            continue
        if r.get("action") not in ("click", "feedback"):
            continue
        sid = str((r.get("meta") or {}).get("strategy_id") or "").strip()
        if sid:
            engaged.add(sid)
    strats = store.all("strategies") or {}
    for s in strats.values():
        if isinstance(s, dict) and s.get("status") == "active":
            engaged.add(s.get("id"))
    series = _per_strategy_series(days)
    rets: list[float] = []
    for sid in engaged:
        s = strats.get(sid) or {}
        if not isinstance(s, dict) or s.get("status") != "active":
            continue
        seq = [p["nav"] for p in series.get(sid, []) if p.get("nav")]
        if len(seq) >= 2 and seq[0] > 0:
            rets.append(seq[-1] / seq[0] - 1)
    if not rets:
        return {
            **base,
            "engaged": len(engaged),
            "note": "参与策略无 ≥2 日影子净值，暂无 outcome 归因",
        }
    avg = sum(rets) / len(rets)
    delta = round(max(-0.05, min(0.05, 0.08 * avg)), 3)
    return {
        "delta": delta,
        "engaged": len(engaged),
        "samples": len(rets),
        "avg_return_pct": round(avg * 100, 2),
        "note": (
            f"参与 {len(engaged)} 个 active 策略影子均收益 {avg * 100:.1f}%，"
            f"outcome 归因强度 {delta:+.3f}（不修改风险画像）"
        ),
    }
