# -*- coding: utf-8 -*-
"""研究任务调度优先级（v1）。

只决定待研究工作先派发哪一条，不改变研究授权、条件判断或联系决定。
分数在任务创建时计算并持久化；同一分数按 `next_run_at` 升序派发，旧的先。
"""

from __future__ import annotations

import json

RESEARCH_PRIORITY_VERSION = "v1"
NEUTRAL_PRIORITY = 50

ACTION_WEIGHTS = {
    "baseline_review": 1.0,
    "due_reminder": 0.9,
    "event_review": 0.8,
    "condition_retry": 0.7,
    "periodic_check": 0.5,
    "scheduled_delivery": 0.4,
}
SCOPE_HELD = 1.0
SCOPE_WATCHED = 0.7
SCOPE_OTHER = 0.4
WEIGHTS = {"action": 0.6, "scope": 0.4}


def _subject_tickers(store, mandate_id: str, revision: int) -> set[str]:
    rows = store._connect().execute(
        "SELECT entity_id FROM mandate_subjects WHERE mandate_id = ? AND revision = ?",
        (mandate_id, revision),
    ).fetchall()
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


def score_for(store, mandate, revision: int, action: str) -> dict:
    """计算一条待研究任务的调度分；异常时回落中性值。"""

    try:
        subjects = _subject_tickers(store, mandate.mandate_id, revision)
        if subjects & _investment_tickers(store, mandate.principal_id, "default"):
            scope = SCOPE_HELD
        elif subjects & _investment_tickers(store, mandate.principal_id, "watchlist"):
            scope = SCOPE_WATCHED
        else:
            scope = SCOPE_OTHER
        factors = {
            "action": ACTION_WEIGHTS.get(action, 0.5),
            "scope": scope,
        }
        value = int(round(100 * sum(WEIGHTS[key] * factors[key] for key in WEIGHTS)))
        return {
            "score": max(0, min(100, value)),
            "version": RESEARCH_PRIORITY_VERSION,
            "factors": factors,
        }
    except Exception:
        return {
            "score": NEUTRAL_PRIORITY,
            "version": RESEARCH_PRIORITY_VERSION,
            "factors": {"action": 0.5, "scope": 0.5},
        }
