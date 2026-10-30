# -*- coding: utf-8 -*-
"""通知队列优先级（v2）。

只影响通知队列的展示顺序和处理顺序，不参与联系决定，也不改变发送集合。
分数是确定性的：相同输入与相同 ``at`` 必得相同结果，不调用模型、不读取
随机数；缺失或计算失败时回落中性值，而不是 0。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

PRIORITY_VERSION = "v2"
NEUTRAL_PRIORITY = 50
BEHAVIOR_WEIGHTS = {"open": 1, "analyze": 2, "follow": 3, "unfollow": -3}

MODE_WEIGHTS = {
    "due_reminder": 1.0,
    "condition": 0.8,
    "periodic_check": 0.5,
    "scheduled_delivery": 0.4,
}
SCOPE_HELD = 1.0
SCOPE_WATCHED = 0.7
SCOPE_OTHER = 0.4
FRESHNESS_HALF_LIFE_SECONDS = 6 * 3600
REPEAT_WINDOW_SECONDS = 24 * 3600
REPEAT_PENALTY = 10
WEIGHTS = {
    "mode": 0.35,
    "scope": 0.25,
    "freshness": 0.15,
    "deadline": 0.10,
    "interest": 0.15,
}


def neutral() -> dict:
    """无法计算时的中性分数；只影响排序，不影响投递。"""

    return {
        "score": NEUTRAL_PRIORITY,
        "version": PRIORITY_VERSION,
        "factors": {"mode": 0.5, "scope": 0.5, "freshness": 0.5, "deadline": 0.5, "interest": 0.5, "repeat": 0},
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _subject_tickers(store, mandate_id: str, revision: int) -> set[str]:
    rows = store._connect().execute(
        "SELECT entity_id FROM mandate_subjects WHERE mandate_id = ? AND revision = ?",
        (mandate_id, revision),
    ).fetchall()
    # 研究对象可能是 SEC:CN:A:600519，也可能直接是代码；只取末段比较。
    return {str(row[0]).rsplit(":", 1)[-1] for row in rows if row and row[0]}


def _investment_tickers(store, principal: str, collection: str) -> set[str]:
    row = store._connect().execute(
        "SELECT document FROM investment_facts WHERE principal = ?", (principal,)
    ).fetchone()
    if not row:
        return set()
    try:
        document = json.loads(row[0])
    except (TypeError, ValueError):
        return set()
    items = document.get(collection) if isinstance(document, dict) else None
    if not isinstance(items, list):
        return set()
    return {
        str(item.get("ticker"))
        for item in items
        if isinstance(item, dict) and item.get("ticker")
    }


def _scope_weight(store, mandate, revision) -> float:
    subjects = _subject_tickers(store, mandate.mandate_id, revision.revision)
    if not subjects:
        return SCOPE_OTHER
    if subjects & _investment_tickers(store, mandate.principal_id, "default"):
        return SCOPE_HELD
    if subjects & _investment_tickers(store, mandate.principal_id, "watchlist"):
        return SCOPE_WATCHED
    return SCOPE_OTHER


def _interest_weight(store, mandate, revision) -> float:
    """本地学习显式开启时，按研究对象的行为信号做温和排序修正。"""

    subjects = _subject_tickers(store, mandate.mandate_id, revision.revision)
    if not subjects:
        return 0.5
    row = store._connect().execute(
        "SELECT document FROM personalization_state WHERE principal = ?",
        (mandate.principal_id,),
    ).fetchone()
    if not row:
        return 0.5
    try:
        document = json.loads(row[0])
    except (TypeError, ValueError):
        return 0.5
    if not isinstance(document, dict):
        return 0.5
    enabled = (
        (document.get("preferences") or {}).get("local_learning") or {}
    ).get("enabled")
    if enabled is not True:
        return 0.5
    behavior = document.get("behavior") or {}
    total = 0
    events = behavior.get("events") if isinstance(behavior, dict) else None
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        context = event.get("context")
        ticker = context.get("ticker") if isinstance(context, dict) else None
        if ticker and str(ticker).rsplit(":", 1)[-1] in subjects:
            total += BEHAVIOR_WEIGHTS.get(event.get("action"), 0)
    feedback = behavior.get("default") if isinstance(behavior, dict) else None
    for record in feedback if isinstance(feedback, list) else []:
        if not isinstance(record, dict) or record.get("action") != "feedback":
            continue
        meta = record.get("meta")
        if not isinstance(meta, dict):
            continue
        if str(meta.get("ticker") or "").rsplit(":", 1)[-1] not in subjects:
            continue
        sentiment = record.get("sentiment")
        total += 3 if sentiment == "useful" else -3 if sentiment == "useless" else 0
    return 0.5 + 0.5 * math.tanh(total / 6)


def _freshness(decision, at: float) -> float:
    age = max(0.0, at - decision.created_at.timestamp())
    return math.exp(-age / FRESHNESS_HALF_LIFE_SECONDS)


def _deadline(decision, at: float) -> float:
    if decision.expires_at is None:
        return 0.5
    remaining = decision.expires_at.timestamp() - at
    if remaining <= 6 * 3600:
        return 1.0
    if remaining <= 24 * 3600:
        return 0.7
    if remaining <= 72 * 3600:
        return 0.4
    return 0.2


def _repeat(store, decision, at: float) -> int:
    since = datetime.fromtimestamp(at - REPEAT_WINDOW_SECONDS, timezone.utc).isoformat()
    row = store._connect().execute(
        "SELECT COUNT(*) FROM contact_decisions "
        "WHERE mandate_id = ? AND condition_key = ? AND created_at >= ? AND decision_id <> ? "
        "AND decision IN ('send', 'aggregate')",
        (decision.mandate_id, decision.condition_key, since, decision.decision_id),
    ).fetchone()
    return int(row[0]) if row else 0


def score_for(decision, mandate, revision, policy, store, at: float) -> dict:
    """计算一条决定在队列中的优先级，返回分数、版本与因子分解。"""

    try:
        factors = {
            "mode": _clamp01(MODE_WEIGHTS.get(policy.mode, MODE_WEIGHTS["condition"])),
            "scope": _clamp01(_scope_weight(store, mandate, revision)),
            "freshness": _clamp01(_freshness(decision, at)),
            "deadline": _clamp01(_deadline(decision, at)),
            "interest": _clamp01(_interest_weight(store, mandate, revision)),
            "repeat": _repeat(store, decision, at),
        }
        weighted = sum(WEIGHTS[key] * factors[key] for key in WEIGHTS)
        value = int(round(100 * weighted - REPEAT_PENALTY * factors["repeat"]))
        return {
            "score": max(0, min(100, value)),
            "version": PRIORITY_VERSION,
            "factors": factors,
        }
    except Exception:
        # 排序是展示层决策；任何异常都不能阻断决定入队或改变发送资格。
        return neutral()
