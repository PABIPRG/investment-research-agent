"""从旧持仓模块精选的规范化与快照算法，不包含行情/服务。"""
import hashlib
import json
from typing import Any

def _positions(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in value:
        position = {
            "ticker": str(item["ticker"]),
            "quantity": float(item["quantity"]),
            "cost_price": float(item["cost_price"]),
        }
        for key in ("trades", "position_time", "time_source"):
            if item.get(key) not in (None, [], ""):
                position[key] = item[key]
        normalized.append(position)
    return sorted(normalized, key=lambda item: item["ticker"])

def _snapshot(
    positions: list[dict[str, Any]],
    source: str,
    effective_at: str,
    previous_snapshot_id: str | None,
) -> dict[str, Any]:
    payload = json.dumps(
        {"effective_at": effective_at, "source": source, "positions": positions},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "snapshot_id": hashlib.blake2s(payload, digest_size=16).hexdigest(),
        "effective_at": effective_at,
        "source": source,
        "positions": positions,
        "previous_snapshot_id": previous_snapshot_id,
    }
