# 来源 9c23b1f adapter/risk_engine.py，原许可见 third-party。
# 迁移修改：使用当前主体的内存快照；无旧文件缓存、行情网络或通知副作用。
import time
from .runtime import settings
from .personalize import _active_strategies,_classify,_holdings_codes,_now,_risk_level,_shadow_snapshot,_watchlist_codes
from .risk_profiles import get_risk_profile

def portfolio_risk(store):
    return _compute_portfolio_risk(store,get_risk_profile())

_SEVERITY_ORDER = {"高": 2, "中": 1, "低": 0}

_BREACH_LABELS = {
    "single_stock_weight": "单股权重",
    "hhi": "集中度 HHI",
    "portfolio_vol": "组合波动率",
}

def _feedback_counts(store) -> dict:
    """近 N 小时反馈记录 → {card_id(预警/卡片 id): {useful, useless}}（V→Q 归因）。"""
    from .runtime import settings
    from .local_telemetry import _parse_ts

    now = time.time()
    win = float(settings.personalized_behavior_hours) * 3600
    out: dict[str, dict] = {}
    seen: set[str] = set()
    for r in store.get("behavior", "default") or []:
        if not isinstance(r, dict) or r.get("action") != "feedback":
            continue
        parsed = _parse_ts(r.get("server_ts") or r.get("ts"))
        if parsed is None:
            continue
        t = parsed.timestamp()
        if (now - t) > win:
            continue
        cid = str(r.get("card_id") or "").strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        d = out.setdefault(cid, {"useful": 0, "useless": 0, "current": None})
        sent = r.get("sentiment")
        if sent in ('useful','useless'):d['current']=sent
        if sent == "useful":
            d["useful"] += 1
            d["current"] = "useful"
        elif sent == "useless":
            d["useless"] += 1
            d["current"] = "useless"
    return out

def _severity(excess: float) -> str:
    """超限倍数 → 严重度：超 1.5 倍高 / 超 1 倍中 / 其余低。"""
    return "高" if excess > 1.5 else ("中" if excess > 1 else "低")

def _excess_ratio(value, limit) -> float | None:
    """value / limit；limit 缺失或非正数返回 None（不产出 breach）。"""
    try:
        l = float(limit)
    except (TypeError, ValueError):
        return None
    if l <= 0:
        return None
    try:
        return float(value) / l
    except (TypeError, ValueError):
        return None

def _compute_portfolio_risk(store, profile_key: str) -> dict:
    """N 组合风险模型的无缓存确定性计算。

    - 持仓 N → 等权 w = 1/N，HHI = 1/N（无价格时等权是唯一诚实假设）；
    - 对比 profile(profile_key)["risk_budget"]：single_stock_weight_max / hhi_max /
      portfolio_vol_max，breach 形状 {indicator,label,value,limit,excess,severity}；
    - 影子回撤/波动：shadow_equity/{date}.overall_nav ≥2 日才评估，否则 null + 数据不足。
    """
    holdings = _holdings_codes(store)
    n = len(holdings)
    w = 1.0 / n if n else 0.0
    hhi = 1.0 / n if n else 0.0

    from .risk_profiles import profile as _profile

    key = profile_key
    p = _profile(profile_key)
    budget = p["risk_budget"]
    as_of = _now()

    # ---- 影子回撤 / 年化波动（≥2 日净值才评估）-------------------------------
    eq = store.all("shadow_equity") or {}
    navs = []
    for date in sorted(eq.keys()):
        try:
            v = float((eq[date] or {}).get("overall_nav"))
        except (TypeError, ValueError):
            continue
        if v > 0:
            navs.append((date, v))

    shadow_max_drawdown = None
    shadow_annualized_vol = None
    data_note = None
    vol_breach = None
    if len(navs) >= 2:
        peak = navs[0][1]
        mdd = 0.0
        for _d, v in navs:
            peak = max(peak, v)
            if peak > 0:
                mdd = max(mdd, (peak - v) / peak)
        shadow_max_drawdown = round(mdd, 4)
        rets = [navs[i][1] / navs[i - 1][1] - 1.0 for i in range(1, len(navs))]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1 if len(rets) > 1 else 1)
        shadow_annualized_vol = round((var ** 0.5) * (252 ** 0.5), 4)
        vol_limit = budget.get("portfolio_vol_max")
        vratio = _excess_ratio(shadow_annualized_vol, vol_limit)
        if vratio is not None and vratio > 1:
            vol_breach = {
                "indicator": "portfolio_vol",
                "label": _BREACH_LABELS["portfolio_vol"],
                "value": shadow_annualized_vol,
                "limit": float(vol_limit),
                "excess": round(vratio, 2),
                "severity": _severity(vratio),
            }
    else:
        data_note = "影子净值不足2日，回撤/波动未评估"

    # ---- 集中度 breaches（单股权重 + HHI）-------------------------------------
    breaches = []
    if n:
        sw_limit = budget.get("single_stock_weight_max")
        sw_ratio = _excess_ratio(w, sw_limit)
        if sw_ratio is not None and sw_ratio > 1:
            breaches.append({
                "indicator": "single_stock_weight",
                "label": _BREACH_LABELS["single_stock_weight"],
                "value": round(w, 4),
                "limit": float(sw_limit),
                "excess": round(sw_ratio, 2),
                "severity": _severity(sw_ratio),
            })
        hi_limit = budget.get("hhi_max")
        hi_ratio = _excess_ratio(hhi, hi_limit)
        if hi_ratio is not None and hi_ratio > 1:
            breaches.append({
                "indicator": "hhi",
                "label": _BREACH_LABELS["hhi"],
                "value": round(hhi, 4),
                "limit": float(hi_limit),
                "excess": round(hi_ratio, 2),
                "severity": _severity(hi_ratio),
            })
    if vol_breach:
        breaches.append(vol_breach)

    return {
        "as_of": as_of,
        "profile": key,
        "profile_label": p["label"],
        "risk_budget": dict(budget),
        "summary": {
            "n_positions": n,
            "equal_weight": round(w, 4),
            "hhi": round(hhi, 4),
            "shadow_max_drawdown": shadow_max_drawdown,
            "shadow_annualized_vol": shadow_annualized_vol,
            "data_note": data_note,
        },
        "breaches": breaches,
    }

def risk_alerts(store=None) -> dict:
    """Q 风险预警中心：聚合 5 源（组合/影子/事件/画像/持仓计划），按严重度排序。

    每项 {id, source, severity, title, detail, codes[], ts, strategy_id?}。
    """
    from .store import JsonStore

    store = store or JsonStore()
    from .risk_profiles import profile as _profile

    pr = portfolio_risk(store)
    key = pr["profile"]
    p = _profile(key)
    budget = p["risk_budget"]
    items: list[dict] = []
    fb_counts = _feedback_counts(store)  # V→Q 效果归因：每预警的 有用/没用 反馈

    # 1) 组合（N）--------------------------------------------------------------
    holdings_codes = list(_holdings_codes(store))
    for b in pr["breaches"]:
        label = b["label"]
        if b["indicator"] == "single_stock_weight":
            detail = f"当前单股等权占比 {b['value']*100:.0f}%，{p['label']}预算上限 {b['limit']*100:.0f}%（超 {b['excess']:.1f} 倍）"
        elif b["indicator"] == "hhi":
            detail = f"当前集中度 HHI={b['value']:.2f}，{p['label']}预算上限 {b['limit']:.2f}（超 {b['excess']:.1f} 倍）"
        else:
            detail = f"影子组合年化波动 {b['value']*100:.0f}%，预算上限 {b['limit']*100:.0f}%（超 {b['excess']:.1f} 倍）"
        items.append({
            "id": "risk-" + _md5("portfolio:" + b["indicator"]),
            "source": "portfolio",
            "severity": b["severity"],
            "title": label + "超预算",
            "detail": detail,
            "codes": holdings_codes,
            "strategy_id": None,
            "ts": pr["as_of"],
        })

    # 2) 影子（I）--------------------------------------------------------------
    snap = _shadow_snapshot(store) or {}
    equity = store.all("shadow_equity") or {}
    latest_errors = {}
    if equity:
        latest = max(equity.keys())
        latest_errors = (equity[latest] or {}).get("strategy_errors") or {}
    for sid, s in snap.items():
        name = s.get("name") or sid
        codes = list(s.get("symbols") or [])
        nav = s.get("nav")
        if nav is not None:
            try:
                nav = float(nav)
            except (TypeError, ValueError):
                nav = None
            if nav is not None and nav < 1.0:
                items.append({
                    "id": "risk-" + _md5("shadow:nav:" + sid),
                    "source": "shadow",
                    "severity": "高" if nav < 0.95 else "中",
                    "title": "影子策略净值回撤",
                    "detail": f"策略「{name}」影子净值 {nav:.4f} < 1，持仓浮亏中",
                    "codes": codes,
                    "strategy_id": sid,
                    "ts": _now(),
                })
        closed = int(s.get("closed_count") or 0)
        if closed > 0:
            net = 0.0
            trade_count = 0
            for k, v in (store.all("shadows") or {}).items():
                if not k.startswith(f"trades:{sid}"):
                    continue
                # trades:{sid} 存的是 list[dict]（shadow.py 平仓台账）；兼容旧版单 dict 形态。
                rows = v if isinstance(v, list) else [v]
                for t in rows:
                    if not isinstance(t, dict):
                        continue
                    trade_count += 1
                    try:
                        net += float(t.get("ret_pct") or 0)
                    except (TypeError, ValueError):
                        pass
            if trade_count and net < 0:
                items.append({
                    "id": "risk-" + _md5("shadow:closed:" + sid),
                    "source": "shadow",
                    "severity": "中",
                    "title": "影子策略已实现亏损",
                    "detail": f"策略「{name}」已平仓 {closed} 笔，累计收益 {net:.1f}%",
                    "codes": codes,
                    "strategy_id": sid,
                    "ts": _now(),
                })
        errs = latest_errors.get(sid) if isinstance(latest_errors, dict) else None
        if errs:
            items.append({
                "id": "risk-" + _md5("shadow:err:" + sid),
                "source": "shadow",
                "severity": "低",
                "title": "影子运行告警",
                "detail": "策略「{}」部分标的行情/下单异常：{}".format(
                    name, "、".join(str(e) for e in list(errs)[:3])),
                "codes": codes,
                "strategy_id": sid,
                "ts": _now(),
            })

    # 3) 事件（F）--------------------------------------------------------------
    from .runtime import settings
    from .strategies import _str2md5, fetch_events_with_status

    holdings_set = set(holdings_codes)
    watchlist_set = set(_watchlist_codes(store))
    actives = _active_strategies(store)
    events, event_status = fetch_events_with_status(
        limit=30,
        timeout=settings.risk_event_deadline,
        allow_stale=True,
        failure_backoff=True,
        cached_impact=True,
    )
    for ev in events or []:
        if str(ev.get("direction") or "") != "利空":
            continue
        bk, mh, mw, _strats = _classify(ev, holdings_set, watchlist_set, actives)
        if bk not in ("holdings", "watchlist"):
            continue
        base = "高" if bk == "holdings" else "中"
        cal = _risk_level(ev, key)["level"]
        sev = base if _SEVERITY_ORDER[base] >= _SEVERITY_ORDER[cal] else cal
        items.append({
            "id": "risk-" + _str2md5("event:" + str(ev.get("id") or "")),
            "source": "event",
            "severity": sev,
            "title": ("持仓" if bk == "holdings" else "自选") + "利空事件",
            "detail": (ev.get("summary") or ev.get("title") or "")[:120],
            "codes": mh or mw,
            "strategy_id": None,
            "ts": ev.get("time") or _now(),
        })

    # 4) 画像（K，advisory 上下文）---------------------------------------------
    items.append({
        "id": "risk-" + _md5("profile:" + key),
        "source": "profile",
        "severity": "低",
        "title": "画像预算提示",
        "detail": "当前画像 {}，组合预算 波动≤{:.0f}% / HHI≤{:.2f}".format(
            p["label"], budget.get("portfolio_vol_max", 0) * 100, budget.get("hhi_max", 0)),
        "codes": [],
        "strategy_id": None,
        "ts": _now(),
    })

    # 5) 持仓计划：只投影 trading-core 已原子接受的触发，不读取行情侧暂存。
    from .position_risk import trigger_alert_items

    items.extend(trigger_alert_items(store))

    # V→Q：反馈只用于效果归因；任何来源的风险严重度都不受内容偏好影响。
    for it in items:
        it["feedback"] = fb_counts.get(it["id"]) or {"useful": 0, "useless": 0, "current": None}

    # R→V 效果漏斗（曝光→点击→有用/没用，观察整体归因）
    from .behavior_profile import behavior_funnel

    items.sort(key=lambda x: (-_SEVERITY_ORDER[x["severity"]], x["source"]))
    return {
        "as_of": _now(),
        "profile": key,
        "profile_label": p["label"],
        "count": len(items),
        "items": items,
        "effect": behavior_funnel(store),
        "degraded": bool(event_status["degraded"]),
        "upstreams": {"market_watch_events": event_status},
    }

def _md5(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
