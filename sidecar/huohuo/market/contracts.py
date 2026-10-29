"""市场查询的限额、数值和来源时间契约。"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from huohuo.contracts import Invalid

CN = ZoneInfo("Asia/Shanghai")
OPERATIONS = {"quotes", "scan", "technical", "news", "brief"}
KINDS = {"gainers", "volume_ratio", "limit", "turnover", "amount"}
TTL = {"quotes": 10, "scan": 20, "technical": 600, "news": 60, "brief": 60}
UNITS = {"price": "CNY/share", "previous_close": "CNY/share", "pct_change": "%",
         "turnover": "%", "volume_ratio": "ratio", "amount_yi": "1e8 CNY", "volume": "share"}


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def source_time(value):
    """无日期的 HH:MM 不猜成今天；国内来源无时区的完整时间按上海解释。"""
    if value in (None, "", "-") or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            n = number(value)
            if n is None or not 946684800 <= n <= 4102444800:
                return None
            dt = datetime.fromtimestamp(n, timezone.utc)
        elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", value):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CN)
        else:
            return None
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def latest_time(values):
    known = [v for v in values if v]
    return max(known) if known else None


def security_code(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:000|001|002|003|300|301|600|601|603|605|688|689)\d{3}", value):
        raise Invalid("行情查询需显式沪深 A 股六位代码；不猜测指数或证券身份")
    return value


def bounded_int(value, minimum, maximum, name):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise Invalid(f"{name} 必须为 {minimum}–{maximum} 的整数")
    return value


def validate(request):
    if not isinstance(request, dict) or request.get("operation") not in OPERATIONS:
        raise Invalid("需指定 quotes、scan、technical、news 或 brief 查询")
    op = request["operation"]
    fields = {"quotes": {"codes", "asset_scope"}, "scan": {"kind", "limit", "min_amount_yi"},
              "technical": {"code", "lookback"}, "news": {"code", "limit", "include_slow"},
              "brief": {"codes", "period", "include_slow"}}[op]
    if set(request) - (fields | {"operation"}):
        raise Invalid("行情查询包含不支持的字段")
    out = {"operation": op}
    if op in {"quotes", "brief"}:
        codes = request.get("codes")
        if not isinstance(codes, list) or not 1 <= len(codes) <= 20:
            raise Invalid("codes 需包含 1–20 只明确证券；不会默认读取自选或扫描全市场")
        if request.get("asset_scope") is not None:
            if op!="quotes" or request["asset_scope"]!="investment":raise Invalid("行情身份范围无效")
            from ..investment.instruments import instrument
            for c in codes:instrument(c)
            out["asset_scope"]="investment"
            out["codes"]=list(dict.fromkeys(codes))
        else:out["codes"] = list(dict.fromkeys(security_code(c) for c in codes))
    if op == "technical":
        out.update(code=security_code(request.get("code")), lookback=bounded_int(request.get("lookback", 120), 20, 250, "lookback"))
    if op == "news":
        if "code" in request:
            out["code"] = security_code(request["code"])
        out["limit"] = bounded_int(request.get("limit", 20), 1, 50, "limit")
    if op in {"news", "brief"}:
        value = request.get("include_slow", False)
        if not isinstance(value, bool) or (op == "news" and "code" in request and value):
            raise Invalid("include_slow 需为布尔值；定向证券新闻不能混入扩展全局快讯")
        out["include_slow"] = value
    if op == "scan":
        if request.get("kind") not in KINDS:
            raise Invalid("scan.kind 需显式指定涨幅、量比、涨跌停候选、换手或成交额排序")
        out.update(kind=request["kind"], limit=bounded_int(request.get("limit", 10), 1, 50, "limit"))
        value = request.get("min_amount_yi", 0)
        n = number(value)
        if isinstance(value, str) or n is None or not 0 <= n <= 10000:
            raise Invalid("min_amount_yi 需为 0–10000 的有限数字，单位亿元")
        out["min_amount_yi"] = n
    if op == "brief":
        if request.get("period") not in {"pre", "post"}:
            raise Invalid("brief.period 需指定 pre（盘前）或 post（盘后）")
        out["period"] = request["period"]
    return out


def envelope(source, data, *, as_of=None, complete=True, warnings=None, status="ok"):
    return {"status": status, "source": source, "as_of": as_of, "time_known": bool(as_of),
            "observed_at": utc_now(), "stale": False, "complete": complete,
            "warnings": warnings or [], "data": data}


def finite_json(value):
    """外部数据的非有限数值保留为未知，不让 JSON 输出 NaN/Infinity。"""
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
