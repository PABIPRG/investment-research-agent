"""迁用旧 market-watch 的东财批量报价和新浪降级；统一成交量为股。"""
from .contracts import UNITS, envelope, latest_time, number, source_time, utc_now
from .http import read, read_json

FIELDS = "f2,f3,f5,f6,f8,f10,f12,f14,f18,f124"
INDICES = {"000001": "1.000001", "399001": "0.399001", "399006": "0.399006", "000300": "1.000300"}


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
    })
    if not isinstance(raw, dict) or raw.get("rc", 0) != 0 or not isinstance(raw.get("data"), dict):
        raise ValueError("invalid eastmoney quote response")
    rows = raw["data"].get("diff")
    if not isinstance(rows, (list, dict)):
        raise ValueError("missing quote rows")
    rows = rows.values() if isinstance(rows, dict) else rows
    return [item for row in rows if isinstance(row, dict) and (item := parse_eastmoney(row, index=indices)) and item["code"] in codes]


def sina(codes, *, indices=False):
    symbols = [("sh" if (INDICES[c][0] == "1" if indices else c.startswith(("5", "6"))) else "sz") + c for c in codes]
    raw = read("https://hq.sinajs.cn/list=" + ",".join(symbols), encoding="gbk", referer="https://finance.sina.com.cn")
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
