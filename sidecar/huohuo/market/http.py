"""固定公开来源的有限读取；TLS 校验不降级，不接受调用方 URL。"""
import json
import requests

HOSTS = {"push2.eastmoney.com", "push2his.eastmoney.com", "hq.sinajs.cn",
         "vip.stock.finance.sina.com.cn", "zhibo.sina.com.cn", "www.cls.cn",
         "search-api-web.eastmoney.com", "quotes.sina.cn", "finance.sina.com.cn",
         "api-one.wallstcn.com", "www.ithome.com", "news.google.com"}


def read(url, params=None, *, encoding="utf-8", referer=None, timeout=(3, 5)):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.port:
        raise ValueError("market source is not allowed")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"}
    if referer:
        headers["Referer"] = referer
    with requests.get(url, params=params, headers=headers, timeout=timeout, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("unexpected source status")
        chunks, length = [], 0
        for chunk in response.iter_content(64 * 1024):
            length += len(chunk)
            if length > 2_000_000:
                raise ValueError("market source response exceeds bound")
            chunks.append(chunk)
        return b"".join(chunks).decode(encoding, errors="replace")


def read_json(url, params=None, **kwargs):
    return json.loads(read(url, params, **kwargs))
