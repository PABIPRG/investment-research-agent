# 来源 9c23b1f adapter/position_risk.py，原许可见 third-party/dsh-trading-core-LICENSE。
# 迁移修改：只保留纯校验/成本投影和建议，不恢复 HTTP 规则端口或旧状态。
from datetime import datetime,timezone

TARGET_KINDS = ("take_profit", "stop_loss")

SUGGESTION_VERSION = 1

PROFILE_SUGGESTIONS = {
    "conservative": {"take_profit_pct": 0.08, "stop_loss_pct": 0.04},
    "balanced": {"take_profit_pct": 0.12, "stop_loss_pct": 0.06},
    "aggressive": {"take_profit_pct": 0.20, "stop_loss_pct": 0.10},
}

class PositionRiskValidationError(ValueError):
    """持仓风险配置或触发载荷不符合领域约束。"""

def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PositionRiskValidationError("时间必须为 ISO-8601 格式") from exc
    if parsed.tzinfo is None:
        raise PositionRiskValidationError("时间必须包含时区")
    return parsed.astimezone(timezone.utc)

def _time_status(config: dict, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    effective_at = _parse_time(config.get("effective_at"))
    expires_at = _parse_time(config.get("expires_at"))
    if effective_at is not None and expires_at is not None and effective_at >= expires_at:
        raise PositionRiskValidationError("到期时间必须晚于生效时间")
    if expires_at is not None and current >= expires_at:
        return "expired"
    if effective_at is not None and current < effective_at:
        return "scheduled"
    return "active"

def suggestion_for_profile(profile_key: str) -> dict:
    """返回显式风险画像对应的确定性、未确认建议。"""
    key = profile_key if profile_key in PROFILE_SUGGESTIONS else "balanced"
    return {
        "profile": key,
        "suggestion_version": SUGGESTION_VERSION,
        "confirmed": False,
        **PROFILE_SUGGESTIONS[key],
    }

def _resolved_price(kind: str, target: dict, cost: float) -> float:
    if target["mode"] == "price":
        result = float(target["value"])
    elif kind == "take_profit":
        result = cost * (1 + float(target["value"]))
    else:
        result = cost * (1 - float(target["value"]))
    if result <= 0:
        raise PositionRiskValidationError("换算后的目标价必须为正数")
    if kind == "take_profit" and result <= cost:
        raise PositionRiskValidationError("止盈目标价必须高于激活时成本")
    if kind == "stop_loss" and result >= cost:
        raise PositionRiskValidationError("止损目标价必须低于激活时成本")
    return round(result, 4)
