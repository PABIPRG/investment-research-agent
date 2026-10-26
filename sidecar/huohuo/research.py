from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .contracts import canonical, scope as validate_scope


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def fetch_snapshot(scope):
    """沿用旧 market-watch 的东财单标的 ulist 路径，不拉取全市场或启动 Agent。"""
    code = scope["entity_id"].rsplit(":", 1)[1]
    secid = ("1." if scope["exchange"] == "SSE" else "0.") + code
    query = urllib.parse.urlencode({"secids": secid, "fltt": "2", "invt": "2", "fields": "f2,f3,f12,f14,f18,f124"})
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    # 不修改用户代理/DNS；错误明确交给调用方，不换源伪装成功。
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("provider response exceeds bound")
    return json.loads(raw), url


def snapshot(scope, loader=fetch_snapshot):
    scope = validate_scope(scope)
    observed_at = utc_now()
    base = {"schema_version": 1, "scope": scope, "observed_at": observed_at,
            "method": "quote_delta_v1", "source": "eastmoney", "limitations": []}
    try:
        raw, url = loader(scope)
        if not isinstance(raw, dict) or raw.get("rc", 0) != 0 or not isinstance(raw.get("data"), dict):
            return {**base, "status": "error", "reason": "provider_rejected_or_malformed", "source_url": url,
                    "source_hash": hashlib.sha256(canonical(raw).encode()).hexdigest(), "raw": raw}
        rows = raw["data"].get("diff")
        code = scope["entity_id"].rsplit(":", 1)[1]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return {**base, "status": "error", "reason": "unexpected_provider_schema", "source_url": url,
                    "source_hash": hashlib.sha256(canonical(raw).encode()).hexdigest(), "raw": raw}
        row = next((r for r in rows if r.get("f12") == code), None)
        if row is None:
            return {**base, "status": "empty", "reason": "security_not_in_response", "source_url": url}
        price, previous = number(row.get("f2")), number(row.get("f18"))
        document = {**base, "source_url": url, "source_hash": hashlib.sha256(canonical(raw).encode()).hexdigest(), "raw": raw}
        if price is None or previous is None or price <= 0 or previous <= 0:
            return {**document, "status": "unavailable", "reason": "required_prices_missing"}
        timestamp = number(row.get("f124"))
        as_of = datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat() if timestamp and timestamp > 0 else None
        if as_of is None:
            document["limitations"].append("来源未提供可用报价时间，不能认定为当前实时行情")
        document["limitations"].append("一次报价快照不代表持续监测，不用于交易执行或完整投资判断")
        return {**document, "status": "ok", "data_as_of": as_of,
                "values": {"name": row.get("f14"), "price": str(price), "previous_close": str(previous),
                           "change": str(price - previous), "change_percent": str(((price - previous) / previous * 100).quantize(Decimal("0.0001"))),
                           "currency": "CNY", "price_unit": "CNY/share", "period": "source_quote_vs_previous_close"}}
    except Exception as exc:
        return {**base, "status": "error", "reason": "provider_failed", "error_type": type(exc).__name__}

