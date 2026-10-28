"""统一查询、限流与短期缓存；来源证据持久化仍由 Sources 负责。"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from .contracts import TTL, envelope, finite_json, source_time, utc_now, validate

MAX_STALE = {"quotes": 600, "scan": 600, "technical": 86400, "news": 3600, "brief": 3600}


def isolated_provider(request, timeout=18):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    completed = subprocess.run(
        [sys.executable, "-m", "huohuo.market.provider"], input=json.dumps(request),
        text=True, capture_output=True, timeout=timeout, env=env, check=True,
    )
    if len(completed.stdout) > 2_000_000:
        raise ValueError("market response exceeds bound")
    return json.loads(completed.stdout)


class MarketData:
    def __init__(self, provider=None, *, clock=time.monotonic, now=utc_now, capacity=4):
        self.provider = provider or isolated_provider
        self.clock, self.now = clock, now
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self._flights = set()
        self._capacity = threading.BoundedSemaphore(capacity)

    def _failure(self, reason, cached, age, operation):
        if cached and age <= MAX_STALE[operation]:
            result = copy.deepcopy(cached)
            result.update(stale=True, complete=False, cache="stale")
            result["warnings"] = list(dict.fromkeys(result["warnings"] + [reason, "返回旧缓存，不能作为当前触发证据"]))
            return result
        return envelope("unavailable", {}, complete=False, status="unavailable", warnings=[reason])

    def _normalize(self, raw, request):
        if not isinstance(raw, dict) or raw.get("status") not in {"ok", "empty", "unavailable"} or not isinstance(raw.get("data"), dict):
            raise ValueError("invalid market provider envelope")
        sanitized = finite_json(raw)
        if json.dumps(raw, sort_keys=True) != json.dumps(sanitized, sort_keys=True):
            sanitized["complete"] = False
            sanitized["warnings"] = list(sanitized.get("warnings", [])) + ["来源包含非有限数值，已标为未知"]
        sanitized.setdefault("warnings", [])
        sanitized.setdefault("source", "unknown")
        sanitized.setdefault("stale", False)
        sanitized.setdefault("complete", False)
        sanitized.setdefault("observed_at", self.now())
        sanitized["as_of"] = source_time(sanitized.get("as_of"))
        sanitized["time_known"] = bool(sanitized["as_of"])
        if request["operation"] == "brief":
            for name in ("quotes", "indices", "news"):
                child = sanitized["data"].get(name)
                if isinstance(child, dict):
                    child = self._normalize(child, {"operation": "news" if name == "news" else "quotes"})
                    sanitized["data"][name] = child
                    if child["stale"]:
                        sanitized["stale"] = True
                    if not child["complete"]:
                        sanitized["complete"] = False
                    sanitized["warnings"].extend(f"{name}：{w}" for w in child["warnings"])
        if request["operation"] == "technical" and sanitized["as_of"]:
            age = (datetime.fromisoformat(self.now()) - datetime.fromisoformat(sanitized["as_of"])).total_seconds()
            if age > 4 * 86400 or age < 0:
                sanitized["stale"] = True
                sanitized["warnings"].append("最新日线超过 4 天或日期异常，可回看但不触发新提醒")
        if request["operation"] in {"quotes", "scan"}:
            now = datetime.fromisoformat(self.now()).astimezone(timezone.utc)
            for row in sanitized["data"].get("items", []):
                stamp = source_time(row.get("as_of"))
                row.update(as_of=stamp, time_known=bool(stamp))
                age = (now - datetime.fromisoformat(stamp)).total_seconds() if stamp else None
                row["stale"] = age is not None and (age > 180 or age < -30)
                if stamp is None:
                    sanitized["complete"] = False
                    sanitized["warnings"].append("部分报价缺少来源时间，不能认定为实时行情")
                if row["stale"]:
                    sanitized["stale"] = True
                    sanitized["warnings"].append("部分报价来源时间超过 3 分钟或异常，不作为当前触发证据")
        sanitized["warnings"] = list(dict.fromkeys(sanitized["warnings"]))
        return sanitized

    def query(self, request):
        request = validate(request)
        operation = request["operation"]
        key = json.dumps(request, sort_keys=True, separators=(",", ":"))
        with self._lock:
            entry = self._cache.get(key)
            age, cached = (self.clock() - entry[0], entry[1]) if entry else (float("inf"), None)
            if cached and age <= TTL[operation]:
                result = copy.deepcopy(cached)
                result["cache"] = "fresh"
                return self._normalize(result, request)
            if key in self._flights or not self._capacity.acquire(blocking=False):
                return self._failure("行情查询正在进行，请稍后重试", cached, age, operation)
            self._flights.add(key)
        try:
            result = self._normalize(self.provider(request), request)
            if result["status"] == "unavailable":
                return self._failure("；".join(result["warnings"]) or "资料源暂不可用", cached, age, operation)
            result["cache"] = "live"
            with self._lock:
                self._cache[key] = (self.clock(), copy.deepcopy(result))
                self._cache.move_to_end(key)
                while len(self._cache) > 128:
                    self._cache.popitem(last=False)
            return result
        except (subprocess.TimeoutExpired, TimeoutError):
            return self._failure("公开资料源请求超时，本次查询已终止", cached, age, operation)
        except Exception as exc:
            return self._failure(f"公开资料源查询失败（{type(exc).__name__}）", cached, age, operation)
        finally:
            with self._lock:
                self._flights.discard(key)
                self._capacity.release()
