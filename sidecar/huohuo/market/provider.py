"""可由父进程强制终止的一次公开资料查询。"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .contracts import CN, envelope, finite_json, latest_time, validate
from .news import fetch_news
from .quotes import INDICES, daily_close, fetch_quotes, is_previous_close
from .scan import fetch_scan
from .technical import fetch_technical


def _pre_close(section, codes, *, indices=False):
    """盘前用前一交易日日线收盘兜底，并保留逐行口径标注。

    09:15 起集合竞价没有成交价，实时快照给不出可核验的昨收；只有日线能提供
    带明确交易日期的收盘。日线行标注 price_basis/time_precision，不冒充当日行情。
    """
    data = section.get("data") if isinstance(section, dict) else None
    rows = data.get("items") if isinstance(data, dict) else None
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    today = datetime.now(CN).date()
    if len(rows) == len(codes) and all(is_previous_close(row, today) for row in rows):
        return section
    names = {row.get("code"): row.get("name") for row in rows}
    try:
        closed = daily_close(codes, indices=indices, names=names)
    except Exception:
        closed = []
    by_code = {row["code"]: row for row in closed}
    for row in rows:
        if row.get("code") in codes and row.get("code") not in by_code and is_previous_close(row, today):
            by_code[row["code"]] = row
    merged = [by_code[code] for code in codes if code in by_code]
    if not merged:
        return section
    warnings = list(section.get("warnings") or [])
    if any(row.get("price_basis") == "daily_close" for row in merged):
        warnings.append("盘前实时快照不能提供前一交易日收盘；改用日线收盘"
                        "（日期精度，不含量比与换手率，不表示当日行情）")
    sources = sorted({str(row["source"]) for row in merged if row.get("source")})
    return envelope("+".join(sources) or str(section.get("source") or "eastmoney:kline"),
                    {"items": merged, "requested_codes": list(codes)},
                    as_of=latest_time(row.get("as_of") for row in merged),
                    complete=len(merged) == len(codes) and all(
                        row.get("time_known") is True and row.get("price") is not None
                        and row.get("previous_close") is not None and row.get("pct_change") is not None
                        for row in merged),
                    warnings=warnings, status="ok")


def brief(request):
    pre = request.get("period") == "pre"

    def quote_section(codes, indices=False):
        section = fetch_quotes(codes, indices=indices)
        return _pre_close(section, codes, indices=indices) if pre else section

    with ThreadPoolExecutor(max_workers=3) as pool:
        # 盘前日线兜底放进同一批线程，避免串在新闻之后顶到子进程截止时间。
        futures = {"quotes": pool.submit(quote_section, request["codes"]),
                   "indices": pool.submit(quote_section, list(INDICES), True),
                   "news": pool.submit(fetch_news, {"limit": 20, "include_slow": request.get("include_slow", False)})}
        sections = {}
        for name, future in futures.items():
            try:
                sections[name] = future.result()
            except Exception:
                sections[name] = envelope(name, {}, status="unavailable", complete=False, warnings=[f"{name} 来源暂不可用"])
    ready = [r for r in sections.values() if r["status"] in {"ok", "empty"}]
    warnings = [f"{name}：{w}" for name, result in sections.items() for w in result["warnings"]]
    warnings.append("盘前/盘后为资料组织目的，不代表定时任务已建立；此处不调用模型、不发送通知")
    return envelope("market_brief", {"period": request["period"], **sections},
                    as_of=latest_time(s["as_of"] for s in sections.values()),
                    complete=all(s["complete"] and s["status"] != "unavailable" for s in sections.values()),
                    status="ok" if ready else "unavailable", warnings=warnings)


def dispatch(request):
    request = validate(request)
    op = request["operation"]
    if op == "quotes":
        return fetch_quotes(request["codes"])
    if op == "scan":
        return fetch_scan(request)
    if op == "technical":
        return fetch_technical(request)
    if op == "news":
        return fetch_news(request)
    return brief(request)


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read(10_000))
        result = dispatch(request)
    except Exception as exc:
        result = envelope("unavailable", {}, status="unavailable", complete=False,
                          warnings=[f"公开市场资料暂不可用（{type(exc).__name__}）"])
    print(json.dumps(finite_json(result), ensure_ascii=False, allow_nan=False))
