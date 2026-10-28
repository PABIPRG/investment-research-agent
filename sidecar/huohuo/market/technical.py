"""有限日线资料和迁入的技术指标；不形成交易建议。"""
from datetime import datetime, timedelta

from .contracts import CN, envelope, number, source_time
from .baostock_daily import fetch_daily as baostock
from .http import read_json
from .quotes import secid


def eastmoney(code, lookback):
    today = datetime.now(CN).date()
    raw = read_json("https://push2his.eastmoney.com/api/qt/stock/kline/get", {
        "secid": secid(code), "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61", "klt": "101", "fqt": "1",
        "beg": (today - timedelta(days=lookback * 2 + 20)).strftime("%Y%m%d"), "end": today.strftime("%Y%m%d"),
    }, timeout=(2, 3))
    if not isinstance(raw, dict) or raw.get("rc", 0) != 0 or not isinstance(raw.get("data"), dict):
        raise ValueError("invalid kline response")
    lines = raw["data"].get("klines")
    if not isinstance(lines, list):
        raise ValueError("missing klines")
    out = []
    for line in lines[-lookback:]:
        fields = line.split(",")
        if len(fields) >= 7:
            volume = number(fields[5])
            out.append({"date": fields[0], "open": number(fields[1]), "close": number(fields[2]), "high": number(fields[3]),
                        "low": number(fields[4]), "volume": volume * 100 if volume is not None else None, "amount": number(fields[6])})
    return out


def sina(code, lookback):
    raw = read_json("https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData", {
        "symbol": ("sh" if code.startswith("6") else "sz") + code, "scale": "240", "ma": "no", "datalen": str(lookback),
    }, timeout=(2, 3))
    if not isinstance(raw, list):
        raise ValueError("invalid sina kline response")
    return [{"date": str(r.get("day", ""))[:10], **{key: number(r.get(key)) for key in ("open", "close", "high", "low", "volume")},
             "amount": None} for r in raw[-lookback:] if isinstance(r, dict)]


def fetch_technical(request):
    import pandas as pd
    from .indicators import compute_indicators, summarize

    code, lookback = request["code"], request["lookback"]
    warnings = ["技术指标描述历史量价，不构成买卖建议；最新日线可能尚未收盘"]
    raw, source, adjustment = [], "eastmoney", "qfq"
    for source, adjustment, fetch in (("eastmoney", "qfq", eastmoney), ("sina", "unadjusted", sina), ("baostock", "qfq", baostock)):
        try:
            raw = fetch(code, lookback)
        except Exception:
            raw = []
        if raw:
            break
        warnings.append(f"{source} 日线暂不可用或为空，尝试后续公开来源")
    if source == "sina" and raw:
        warnings.append("前复权来源不可用，新浪返回未复权日线；不可与前复权基准直接比较，成交额保持未知")
    if source == "baostock":
        warnings.append("Baostock 为匿名公共明文 TCP 来源，非 TLS；仅发送公开证券代码和日期，不传用户凭据")
    rows = []
    for row in raw:
        row = {"date": row.get("date"), **{k: number(row.get(k)) for k in ("open", "high", "low", "close", "volume", "amount")}}
        for key in ("volume", "amount"):
            if row[key] is not None and row[key] < 0:
                row[key] = None
        try:
            date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError, KeyError):
            continue
        if date > datetime.now(CN).date() or any(row.get(k) is None or row[k] <= 0 for k in ("open", "high", "low", "close")):
            continue
        if row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(row["open"], row["close"]):
            continue
        rows.append(row)
    rows = sorted({r["date"]: r for r in rows}.values(), key=lambda r: r["date"])[-lookback:]
    complete = (len(rows) == lookback and len(raw) == len(rows) and adjustment == "qfq"
                and all(r.get("volume") is not None and r.get("amount") is not None for r in rows))
    if any(r.get("volume") is None for r in rows):
        warnings.append("部分日线成交量未知，量价指标不能作为完整证据")
    if len(rows) != len(raw):
        warnings.append("已排除无效日期或 OHLC 行，结果不完整")
    if len(rows) < lookback:
        warnings.append(f"请求 {lookback} 根日线，仅取得 {len(rows)} 根；窗口不足的指标保持未知")
    if not rows:
        return envelope(source, {"code": code, "bars": [], "indicators": {}, "summary": []}, status="unavailable", complete=False, warnings=warnings)
    indicators = compute_indicators(pd.DataFrame(rows))
    through = rows[-1]["date"]
    data = {"code": code, "bars": rows, "through": through, "lookback": lookback, "adjustment": adjustment,
            "indicators": indicators, "summary": summarize(indicators), "time_precision": "date",
            "transport": "plain_tcp_public" if source == "baostock" else "https",
            "units": {"open": "CNY/share", "close": "CNY/share", "high": "CNY/share", "low": "CNY/share", "volume": "share", "amount": "CNY"}}
    return envelope(source, data, as_of=source_time(through + " 00:00:00"), complete=complete, warnings=warnings)
