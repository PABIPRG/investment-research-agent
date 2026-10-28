"""交易日历覆盖区间内才回答；失败和区间外绝不按星期猜测。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import utc_now
from .http import read

SOURCE_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"


class CalendarUnavailable(RuntimeError):
    pass


def fetch_calendar():
    """复用 AKShare 静态解码器，网络文本只作为数据，不执行来源脚本。"""
    from akshare.stock.cons import hk_js_decode
    from py_mini_racer import MiniRacer
    import pandas as pd

    raw = read(SOURCE_URL)
    if re.fullmatch(r"[\d\s]+", raw):
        days = sorted({datetime.strptime(s, "%Y%m%d").date().isoformat() for s in raw.split()})
    else:
        match = re.fullmatch(r'\s*(?:var\s+)?\w+\s*=\s*"([A-Za-z0-9+/=]+)"\s*;?\s*(?:var\s+\w+\s*=\s*\w+\s*;\s*)?', raw)
        if not match:
            raise CalendarUnavailable("交易日历格式无法识别")
        engine = MiniRacer()
        engine.eval(hk_js_decode)
        decoded = engine.call("d", match.group(1))
        days = sorted({pd.Timestamp(v).date().isoformat() for v in decoded})
    if len(days) < 1000:
        raise CalendarUnavailable("交易日历疑似截断，拒绝猜测缺失日期")
    # AKShare 明确记录的新浪历史缺日补正；不推断未来节假日。
    if days[0] <= "1992-05-04" <= days[-1]:
        days = sorted(set(days) | {"1992-05-04"})
    return {"source": "sina", "source_url": SOURCE_URL, "observed_at": utc_now(),
            "coverage_start": days[0], "coverage_end": days[-1], "trading_days": days}


def isolated_calendar():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    result = subprocess.run([sys.executable, "-m", "huohuo.market.calendar"], capture_output=True,
                            text=True, timeout=12, check=True, env=env)
    if len(result.stdout) > 1_000_000:
        raise CalendarUnavailable("交易日历超过读取上限")
    return json.loads(result.stdout)


class TradingCalendar:
    def __init__(self, cache_path=None, loader=None, *, now=utc_now):
        self.path = Path(cache_path) if cache_path is not None else None
        self.loader = loader or isolated_calendar
        self.now = now
        self._lock = threading.RLock()
        self._document = None
        self._retry_at = 0
        if self.path and self.path.is_file():
            try:
                if self.path.stat().st_size <= 1_000_000:
                    self._document = self._validate(json.loads(self.path.read_text()))
            except (OSError, ValueError, KeyError, TypeError, CalendarUnavailable):
                self._document = None

    def _validate(self, data):
        if not isinstance(data, dict) or data.get("source_url") != SOURCE_URL:
            raise CalendarUnavailable("交易日历缓存来源不匹配")
        days = data.get("trading_days")
        if not isinstance(days, list) or not days or len(days) > 100000:
            raise CalendarUnavailable("交易日历缺少交易日")
        days = sorted({date.fromisoformat(d).isoformat() for d in days})
        if data.get("coverage_start") != days[0] or data.get("coverage_end") != days[-1]:
            raise CalendarUnavailable("交易日历覆盖区间不匹配")
        stamp = datetime.fromisoformat(data["observed_at"])
        if stamp.tzinfo is None:
            raise CalendarUnavailable("交易日历缺少采集时区")
        return {**data, "trading_days": days}

    def _persist(self, data):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                name = stream.name
                os.chmod(name, 0o600)
                json.dump(data, stream, ensure_ascii=False)
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def refresh(self, *, force=False):
        """只能在业务事务之外调用；网络/落盘不会藏在 is_trading_day 中。"""
        with self._lock:
            now = datetime.fromisoformat(self.now()).astimezone(timezone.utc)
            doc = self._document
            age = (now - datetime.fromisoformat(doc["observed_at"])).total_seconds() if doc else float("inf")
            if (age > 86400 or force) and now.timestamp() >= self._retry_at:
                try:
                    updated = self._validate(self.loader())
                    self._persist(updated)
                    doc = self._document = updated
                    age = (now - datetime.fromisoformat(doc["observed_at"])).total_seconds()
                except Exception:
                    self._retry_at = now.timestamp() + 60
            if doc is None or age < -60 or age > 7 * 86400:
                raise CalendarUnavailable("交易日历不可用或缓存超过 7 天；尚不能判断是否交易日")
            return {**doc, "trading_days": list(doc["trading_days"]), "cache_stale": age > 86400}

    def is_trading_day(self, day: date) -> bool:
        """只读内存快照；未知不返回 false，也不做隐式外部 I/O。"""
        if not isinstance(day, date) or isinstance(day, datetime):
            raise CalendarUnavailable("需传入明确交易日期")
        # 不取得 refresh 的网络锁：指针替换是原子的，事务无需等待网络请求。
        doc = self._document
        now = datetime.fromisoformat(self.now()).astimezone(timezone.utc)
        age = (now - datetime.fromisoformat(doc["observed_at"])).total_seconds() if doc else float("inf")
        if doc is None or age < -60 or age > 7 * 86400:
            raise CalendarUnavailable("交易日历尚未刷新或缓存超过 7 天，请在事务外刷新")
        if not doc["coverage_start"] <= day.isoformat() <= doc["coverage_end"]:
            raise CalendarUnavailable("日期超出已核对交易日历覆盖区间")
        return day.isoformat() in doc["trading_days"]


if __name__ == "__main__":
    print(json.dumps(fetch_calendar(), ensure_ascii=False))
