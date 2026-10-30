"""迁用旧 market-watch 的东财批量报价和新浪降级；统一成交量为股。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta

from .contracts import CN, UNITS, envelope, latest_time, number, source_time, utc_now
from .http import read, read_json

FIELDS = "f2,f3,f5,f6,f8,f10,f12,f14,f18,f124"
INDICES = {"000001": "1.000001", "399001": "0.399001", "399006": "0.399006", "000300": "1.000300"}
INDEX_NAMES = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指", "000300": "沪深300"}


def secid(code):
    return ("1." if code.startswith(("5", "6")) else "0.") + code


def parse_eastmoney(row, *, index=False):
    code = str(row.get("f12", ""))
    if len(code) != 6 or not code.isdigit():
        return None
    amount, volume, price = number(row.get("f6")), number(row.get("f5")), number(row.get("f2"))
    as_of = source_time(row.get("f124"))
    units = dict(UNITS)
    if index:
        units.update(price="point", previous_close="point", volume="source_lot")
    return {"code": code, "name": str(row.get("f14") or code), "price": price if price and price > 0 else None,
            "previous_close": number(row.get("f18")), "pct_change": number(row.get("f3")),
            "volume_ratio": number(row.get("f10")), "turnover": number(row.get("f8")),
            "amount_yi": amount / 1e8 if amount is not None else None,
            "volume": volume * (1 if index else 100) if volume is not None else None,
            "source": "eastmoney", "source_url": "https://quote.eastmoney.com/", "units": units,
            "as_of": as_of, "time_known": bool(as_of), "observed_at": utc_now()}


def eastmoney(codes, *, indices=False):
    raw = read_json("https://push2.eastmoney.com/api/qt/ulist.np/get", {
        "secids": ",".join(INDICES[c] if indices else secid(c) for c in codes),
        "fltt": "2", "invt": "2", "fields": FIELDS,
    }, retry_timeouts=True)
    if not isinstance(raw, dict) or raw.get("rc", 0) != 0 or not isinstance(raw.get("data"), dict):
        raise ValueError("invalid eastmoney quote response")
    rows = raw["data"].get("diff")
    if not isinstance(rows, (list, dict)):
        raise ValueError("missing quote rows")
    rows = rows.values() if isinstance(rows, dict) else rows
    return [item for row in rows if isinstance(row, dict) and (item := parse_eastmoney(row, index=indices)) and item["code"] in codes]


def sina(codes, *, indices=False):
    symbols = [("sh" if (INDICES[c][0] == "1" if indices else c.startswith(("5", "6"))) else "sz") + c for c in codes]
    raw = read("https://hq.sinajs.cn/list=" + ",".join(symbols), encoding="gbk",
               referer="https://finance.sina.com.cn", retry_timeouts=True)
    out = []
    for line in raw.splitlines():
        symbol, sep, payload = line.partition('="')
        code = symbol.strip().split("hq_str_")[-1][2:]
        if not sep or code not in codes:
            continue
        fields = payload.rstrip('";').split(",")
        if len(fields) < 32:
            continue
        price, previous = number(fields[3]), number(fields[2])
        amount = number(fields[9])
        stamp = source_time(fields[30] + " " + fields[31])
        units = dict(UNITS)
        if indices:
            units.update(price="point", previous_close="point", volume="source_volume")
        # 停牌/盘前 price=0 不伪装成前收盘的当前价。
        price = price if price and price > 0 else None
        out.append({"code": code, "name": fields[0], "price": price, "previous_close": previous,
                    "pct_change": round((price / previous - 1) * 100, 4) if price and previous and previous > 0 else None,
                    "volume_ratio": None, "turnover": None, "amount_yi": amount / 1e8 if amount is not None else None,
                    "volume": number(fields[8]), "source": "sina", "source_url": "https://finance.sina.com.cn/",
                    "units": units, "as_of": stamp, "time_known": bool(stamp), "observed_at": utc_now()})
    if not out and "hq_str_" not in raw:
        raise ValueError("invalid sina quote response")
    return out


def fetch_quotes(codes, *, indices=False):
    warnings, rows = [], []
    try:
        rows = eastmoney(codes, indices=indices)
    except Exception:
        warnings.append("东方财富报价暂不可用，尝试新浪报价")
    present = {r["code"] for r in rows if r.get("price") is not None}
    missing = [code for code in codes if code not in present]
    if missing:
        try:
            fallback = sina(missing, indices=indices)
            valid = {r["code"]: r for r in fallback if r["price"] is not None}
            rows = [r for r in rows if r["code"] not in valid] + list(valid.values())
        except Exception:
            warnings.append("新浪报价暂不可用")
    by_code = {r["code"]: r for r in rows}
    rows = [by_code[c] for c in codes if c in by_code]
    missing = [c for c in codes if c not in by_code or by_code[c]["price"] is None]
    if missing:
        warnings.append("部分证券缺少有效报价：" + "、".join(missing))
    if any(r["source"] == "sina" for r in rows):
        warnings.append("新浪降级报价不提供量比与换手率，相关值保持未知")
    complete = not missing and all(r["time_known"] for r in rows)
    if not indices:
        complete = complete and all(all(r.get(field) is not None for field in UNITS) for r in rows)
    if rows and not complete:
        warnings.append("报价存在字段或来源时间缺口；仅使用身份、时间及单位均可核验的字段")
    source = "+".join(sorted({r["source"] for r in rows})) or "eastmoney+sina"
    return envelope(source, {"items": rows, "requested_codes": codes, "missing_codes": missing},
                    as_of=latest_time(r["as_of"] for r in rows), complete=complete,
                    warnings=warnings, status="ok" if rows else "unavailable")


def is_previous_close(row, today):
    """报价来源时间是否为今天之前的收盘时点（可用于盘前昨收口径）。"""
    stamp = row.get("as_of")
    try:
        when = datetime.fromisoformat(stamp).astimezone(CN)
    except (TypeError, ValueError):
        return False
    return row.get("time_known") is True and when.date() < today and when.time() >= time(15)


def _kline(code, indices):
    """取最近若干根日线收盘；东财失败再试新浪，都失败返回空列表。"""
    symbol = ("sh" if (INDICES[code][0] == "1" if indices else code.startswith(("5", "6"))) else "sz") + code
    today = datetime.now(CN).date()
    attempts = (
        ("https://push2his.eastmoney.com/api/qt/stock/kline/get", {
            "secid": INDICES[code] if indices else secid(code), "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57", "klt": "101", "fqt": "1",
            "beg": (today - timedelta(days=20)).strftime("%Y%m%d"), "end": today.strftime("%Y%m%d"),
        }),
        ("https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData", {
            "symbol": symbol, "scale": "240", "ma": "no", "datalen": "5",
        }),
    )
    for url, params in attempts:
        try:
            raw = read_json(url, params, timeout=(2, 3), retry_timeouts=True)
        except Exception:
            continue
        if isinstance(raw, dict):
            rows = (raw.get("data") or {}).get("klines") if isinstance(raw.get("data"), dict) else None
        else:
            rows = raw if isinstance(raw, list) else None
        if not isinstance(rows, list):
            continue
        bars = []
        for row in rows:
            if isinstance(row, str):
                fields = row.split(",")
                if len(fields) < 7:
                    continue
                date, close, volume, amount = fields[0], number(fields[2]), number(fields[5]), number(fields[6])
            elif isinstance(row, dict):
                date, close = str(row.get("day", ""))[:10], number(row.get("close"))
                volume, amount = number(row.get("volume")), None
            else:
                continue
            # 当日未收盘的日线不当作昨收；只取今天之前已完成的交易日。
            if date and date < today.isoformat() and close is not None and close > 0:
                bars.append({"date": date, "close": close, "volume": volume, "amount": amount})
        if len(bars) >= 2:
            return bars
    return []


def daily_close(codes, *, indices=False, names=None):
    """前一交易日收盘行（日期精度）；只读公开日线，不冒充当日行情。

    盘前集合竞价阶段没有成交价，实时快照拿不到可核验的昨收；日线是这时
    唯一干净、带明确交易日期的收盘来源。
    """
    names = names if isinstance(names, dict) else {}
    codes = list(codes)

    def series_for(code):
        try:
            return _kline(code, indices)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(codes)))) as pool:
        series = list(pool.map(series_for, codes))
    rows = []
    for code, bars in zip(codes, series):
        if len(bars) < 2:
            continue
        last, previous = bars[-1], bars[-2]
        price, prior = last["close"], previous["close"]
        if price <= 0 or prior <= 0:
            continue
        stamp = source_time(last["date"] + " 00:00:00")
        if stamp is None:
            continue
        units = dict(UNITS)
        if indices:
            units.update(price="point", previous_close="point", volume="source_lot")
        amount = last.get("amount")
        volume = last.get("volume")
        rows.append({
            "code": code,
            "name": names.get(code) or (INDEX_NAMES.get(code) if indices else code),
            "price": price, "previous_close": prior,
            "pct_change": round((price / prior - 1) * 100, 4),
            "volume_ratio": None, "turnover": None,
            "amount_yi": amount / 1e8 if amount is not None else None,
            "volume": None if indices else (volume * 100 if volume is not None else None),
            "source": "eastmoney:kline", "source_url": "https://quote.eastmoney.com/",
            "units": units, "as_of": stamp, "time_known": True, "observed_at": utc_now(),
            "time_precision": "date", "price_basis": "daily_close",
        })
    return rows
