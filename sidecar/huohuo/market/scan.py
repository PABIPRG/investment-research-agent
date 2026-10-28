"""全市场服务端排名的有界候选扫描；只接受显式 scan 请求。"""
from concurrent.futures import ThreadPoolExecutor

from .contracts import UNITS, envelope, latest_time, number, utc_now
from .http import read_json
from .quotes import FIELDS, parse_eastmoney

FS = "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23"
FIELDS_BY_KIND = {"gainers": ("f3", "pct_change"), "volume_ratio": ("f10", "volume_ratio"),
                  "turnover": ("f8", "turnover"), "amount": ("f6", "amount_yi"), "limit": ("f3", "pct_change")}


def eastmoney(kind, count, ascending=False):
    raw = read_json("https://push2.eastmoney.com/api/qt/clist/get", {
        "pn": "1", "pz": str(count), "po": "0" if ascending else "1", "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281", "fltt": "2", "invt": "2",
        "fid": FIELDS_BY_KIND[kind][0], "fs": FS, "fields": FIELDS,
    })
    if not isinstance(raw, dict) or raw.get("rc", 0) != 0 or not isinstance(raw.get("data"), dict):
        raise ValueError("invalid scan response")
    rows = raw["data"].get("diff")
    if not isinstance(rows, list):
        raise ValueError("invalid scan rows")
    return [item for row in rows if isinstance(row, dict) and (item := parse_eastmoney(row))]


def sina(kind, count, ascending=False):
    if kind == "volume_ratio":
        raise ValueError("sina does not provide volume ratio")
    sort = {"gainers": "changepercent", "limit": "changepercent", "turnover": "turnoverratio", "amount": "amount"}[kind]
    raw = read_json("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData", {
        "page": "1", "num": str(count), "sort": sort, "asc": "1" if ascending else "0", "node": "hs_a", "_s_r_a": "init",
    })
    if not isinstance(raw, list):
        raise ValueError("invalid sina scan rows")
    rows = []
    for row in raw:
        code = str(row.get("code", ""))
        if len(code) != 6 or not code.isdigit():
            continue
        amount = number(row.get("amount"))
        rows.append({"code": code, "name": str(row.get("name") or code), "price": number(row.get("trade")),
                     "pct_change": number(row.get("changepercent")), "turnover": number(row.get("turnoverratio")),
                     "volume_ratio": None, "volume": number(row.get("volume")), "amount_yi": amount / 1e8 if amount is not None else None,
                     "as_of": None, "time_known": False, "observed_at": utc_now(), "source": "sina", "units": dict(UNITS)})
    return rows


def fetch_scan(request):
    kind, limit = request["kind"], request["limit"]
    count = 100 if kind == "limit" else min(150, max(limit, limit * 3 if request["min_amount_yi"] else limit))
    warnings = []

    def load(loader):
        if kind != "limit":
            return loader(kind, count)
        with ThreadPoolExecutor(max_workers=2) as pool:
            up = pool.submit(loader, kind, count)
            down = pool.submit(loader, kind, count, True)
            return up.result() + down.result()

    source, complete = "eastmoney", True
    try:
        rows = load(eastmoney)
    except Exception:
        if kind == "volume_ratio":
            return envelope("eastmoney", {}, status="unavailable", complete=False, warnings=["量比数据源不可用，新浪不提供该字段"])
        rows = load(sina)
        source, complete = "sina", False
        warnings.append("东方财富不可用，新浪降级无完整来源日期与量比；不作为实时告警依据")
    # 不让缺失数值进入排序，零值正常保留。
    field = FIELDS_BY_KIND[kind][1]
    unique = {r["code"]: r for r in rows}
    rows = [r for r in unique.values() if r.get(field) is not None]
    if request["min_amount_yi"]:
        rows = [r for r in rows if r.get("amount_yi") is not None and r["amount_yi"] >= request["min_amount_yi"]]
        warnings.append(f"成交额过滤仅覆盖本次排名前 {count} 条候选，不是全量穷举")
        complete = False
    data = {"kind": kind, "universe": "沪深 A 股服务端排名", "candidate_limit": count, "items": []}
    if kind == "limit":
        # 不用涨幅近似值冒充交易所涨跌停状态；新股、ST、价格取整规则不能凭单快照确认。
        for row in rows:
            threshold = 19 if row["code"].startswith(("300", "301", "688", "689")) else 4.5 if "ST" in row["name"].upper() else 9.5
            row["limit_candidate"] = "up" if row["pct_change"] >= threshold else "down" if row["pct_change"] <= -threshold else None
        up = sorted([r for r in rows if r["limit_candidate"] == "up"], key=lambda r: -r[field])[:limit]
        down = sorted([r for r in rows if r["limit_candidate"] == "down"], key=lambda r: r[field])[:limit]
        data.update(items=up + down, limit_up=up, limit_down=down)
        warnings.append("涨跌停为涨幅阈值候选，非交易所确认；各取排名前 100 条，可能遗漏其他候选")
        complete = False
    else:
        data["items"] = sorted(rows, key=lambda r: r[field], reverse=True)[:limit]
    complete = complete and all(r["time_known"] for r in data["items"])
    return envelope(source, data, as_of=latest_time(r["as_of"] for r in data["items"]), complete=complete,
                    warnings=warnings, status="ok" if data["items"] else "empty")
