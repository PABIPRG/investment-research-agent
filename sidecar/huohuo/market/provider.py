"""可由父进程强制终止的一次公开资料查询。"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .contracts import envelope, finite_json, latest_time, validate
from .news import fetch_news
from .quotes import INDICES, fetch_quotes
from .scan import fetch_scan
from .technical import fetch_technical


def brief(request):
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {"quotes": pool.submit(fetch_quotes, request["codes"]),
                   "indices": pool.submit(fetch_quotes, list(INDICES), indices=True),
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
