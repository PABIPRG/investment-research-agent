from __future__ import annotations

import json
import re


class Invalid(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def text(value, name, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Invalid(f"invalid {name}")
    return value


def scope(value):
    keys = {"entity_id", "exchange", "operation"}
    if isinstance(value, dict) and value.get("operation") == "financial_summary": keys |= {"period", "metric", "basis"}
    if not isinstance(value, dict) or set(value) != keys:
        raise Invalid("scope requires entity_id, exchange and operation")
    entity = value["entity_id"]
    if not isinstance(entity, str) or not re.fullmatch(r"SEC:CN:A:[0-9]{6}", entity):
        raise Invalid("unsupported entity_id")
    code = entity.rsplit(":", 1)[1]
    # 本批是受限证券入口，不是完整证券主数据服务；尤其不能将 399 指数视为个股。
    expected = "SSE" if code.startswith(("600", "601", "603", "605", "688", "689")) else "SZSE" if code.startswith(("000", "001", "002", "003", "300", "301")) else None
    if expected is None or value["exchange"] != expected:
        raise Invalid("first batch supports explicit SSE/SZSE A shares only")
    if value["operation"] not in ("quote_snapshot", "company_profile", "financial_summary"):
        raise Invalid("unsupported operation")
    if value["operation"] == "financial_summary":
        if not isinstance(value["period"], str) or not re.fullmatch(r"20[0-9]{2}(0331|0630|0930|1231)", value["period"]): raise Invalid("explicit reporting period required")
        text(value["metric"], "metric", 100)
        if value["basis"] != "source_abstract": raise Invalid("only source abstract basis is supported")
    return dict(value)

