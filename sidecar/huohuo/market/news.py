"""定向东财新闻与新浪/财联社快讯；只取资料，不自行摘要或推送。"""
import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlsplit, urlunsplit

from .contracts import envelope, latest_time, source_time, utc_now
from .http import read, read_json
from .news_feeds import extended_sources


def clean(value, limit=12000):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()[:limit]


def safe_url(value):
    try:
        parts = urlsplit(str(value or ""))
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
            return ""
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
    except ValueError:
        return ""


def item(title, content, url, published, source, *, provider, source_url, code=None):
    title, content = clean(title, 500), clean(content)
    title = title or content[:90]
    if not title:
        return None
    url = safe_url(url)
    stamp = source_time(published)
    # 采集时间不能进入身份 hash；未知时间也保持稳定。
    identity = json.dumps([url or source_url, stamp, title], ensure_ascii=False, separators=(",", ":"))
    return {"id": "NEWS_" + hashlib.sha256(identity.encode()).hexdigest(), "title": title,
            "content": content or title, "url": url or None, "source": clean(source, 100) or provider,
            "provider": provider, "source_url": source_url, "published_at": stamp,
            "time_known": bool(stamp), "observed_at": utc_now(), **({"code": code} if code else {})}


def directed(code, limit):
    """东方财富按证券代码的资讯列表；只有标题/时间/链接，不含正文。

    原 search-api-web 搜索接口已改返回 passportWeb，且不再给出文章列表；
    这里改用东方财富自己行情页使用的 list API，market 前缀 1=沪、0=深。
    """
    market = "1" if code.startswith("6") else "0" if code.startswith(("0", "3")) else ""
    if not market:
        raise ValueError("unsupported code for directed news")
    url = "https://np-listapi.eastmoney.com/comm/web/getListInfo"
    raw = read_json(url, {"client": "web", "mTypeAndCode": f"{market}.{code}", "type": "1",
                          "pageSize": str(limit), "pageIndex": "1"},
                    referer="https://quote.eastmoney.com/")
    rows = (raw.get("data") or {}).get("list")
    if not isinstance(rows, list):
        raise ValueError("invalid directed news response")
    return [n for row in rows[:limit] if isinstance(row, dict) and (n := item(
        row.get("Art_Title"), None, row.get("Art_OriginUrl") or row.get("Art_Url"),
        row.get("Art_ShowTime"), "东方财富", provider="eastmoney", source_url=url, code=code))]


def sina_stock(code, limit):
    """新浪个股资讯页：按代码定向，只有标题/时间/链接，不含正文。"""
    prefix = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else ""
    if not prefix:
        raise ValueError("unsupported code for sina stock news")
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{prefix}{code}.phtml"
    # 该页约 58KB，新浪首字节常在 6—8 秒，默认 5 秒读超时会白白失败。
    block = re.search(r'<div class="datelist">(.*?)</div>', read(url, encoding="gbk", timeout=(6, 12)), re.S)
    if block is None:
        raise ValueError("invalid sina stock news response")
    rows = re.findall(
        r"""(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})&nbsp;&nbsp;<a[^>]*href=['"]([^'"]+)['"][^>]*>([^<]+)</a>""",
        block.group(1),
    )
    return [n for day, clock, href, title in rows[:limit] if (n := item(
        title, None, href, f"{day} {clock}", "新浪财经",
        provider="sina", source_url=url, code=code))]


def sina(limit):
    url = "https://zhibo.sina.com.cn/api/zhibo/feed"
    raw = read_json(url, {"page": "1", "page_size": str(max(limit, 20)), "zhibo_id": "152", "tag_id": "0", "dire": "f", "dpc": "1"})
    rows = raw.get("result", {}).get("data", {}).get("feed", {}).get("list")
    if not isinstance(rows, list):
        raise ValueError("invalid sina news response")
    return [n for row in rows[:limit] if isinstance(row, dict) and (n := item(
        None, row.get("rich_text"), row.get("docurl"), row.get("create_time"), "新浪财经",
        provider="sina", source_url=url))]


def cls(limit):
    url = "https://www.cls.cn/v1/roll/get_roll_list"
    params = {"app": "CailianpressWeb", "category": "", "last_time": int(time.time()),
              "os": "web", "refresh_type": "1", "rn": str(max(20, limit)), "sv": "8.4.6"}
    params["sign"] = hashlib.md5(hashlib.sha1(urlencode(params).encode()).hexdigest().encode()).hexdigest()
    raw = read_json(url, params, referer="https://www.cls.cn/telegraph")
    rows = raw.get("data", {}).get("roll_data")
    if not isinstance(rows, list):
        raise ValueError("invalid cls news response")
    return [n for row in rows[:limit] if isinstance(row, dict) and (n := item(
        row.get("title"), row.get("content"), f"https://www.cls.cn/detail/{row['id']}" if str(row.get("id", "")).isdigit() else None,
        row.get("ctime"), "财联社", provider="cls", source_url=url))]


def fetch_news(request):
    limit, code = request.get("limit", 20), request.get("code")
    warnings, items, successful, sources = [], [], [], []
    selected = (
        {"eastmoney": lambda n: directed(code, n), "sina": lambda n: sina_stock(code, n)}
        if code else {"sina": sina, "cls": cls}
    )
    if request.get("include_slow") and not code:
        selected.update(extended_sources())
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {name: pool.submit(fetch, limit) for name, fetch in selected.items()}
        for name, future in futures.items():
            try:
                rows = future.result()
                items.extend(rows)
                successful.append(name)
                sources.append({"source": name, "status": "ok" if rows else "empty", "count": len(rows)})
            except Exception:
                sources.append({"source": name, "status": "unavailable", "count": 0})
                warnings.append(f"{name} 新闻源暂不可用，本次仅提供其他成功来源")
    if code:
        warnings.append("按证券代码搜索的相关文章，相关性仍需核对原文；不等于公司正式公告")
    items = list({n["id"]: n for n in items}.values())
    items.sort(key=lambda n: n["published_at"] or "", reverse=True)
    items = items[:limit]
    known = all(n["time_known"] for n in items)
    if not known:
        warnings.append("部分新闻未提供可识别的发布时间；不以采集时间代替发布事件时间")
    data = {"items": items, "limit": limit, "code": code, "sources": sources,
            "tier": "directed" if code else "extended" if request.get("include_slow") else "fast",
            "window": "各源最新一页，合并去重后按发布时间取前 limit 条；扩展 Google 仅最近一天搜索，非历史穷举"}
    return envelope("+".join(successful) or "+".join(selected), data,
                    as_of=latest_time(n["published_at"] for n in items),
                    complete=known and len(successful) == len(selected), warnings=warnings,
                    status="ok" if items else "empty" if successful else "unavailable")
