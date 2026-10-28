"""显式扩展新闻：固定华尔街见闻、IT之家 RSS 和两项 Google News 搜索。"""
import json
import os
import subprocess
import sys
import threading
from email.utils import parsedate_to_datetime
from functools import partial

from lxml import etree

from .contracts import bounded_int
from .http import read, read_json

WALLSTREETCN = 'https://api-one.wallstcn.com/apiv1/content/lives'
ITHOME = 'https://www.ithome.com/rss/'
GOOGLE = 'https://news.google.com/rss/search'
GOOGLE_SITES = {'36kr': ('36kr.com', '36氪'), 'huxiu': ('huxiu.com', '虎嗅')}


def published(value):
    try:
        stamp = parsedate_to_datetime(value)
        return stamp.isoformat() if stamp.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_rss(text, *, provider, source_url, label, limit):
    from .news import item
    limit = bounded_int(limit, 1, 50, 'limit')
    encoded = text.encode('utf-8')
    # 禁止 DTD/实体；不解析外部文件或网络，不展开压缩/XML 巨树。
    if len(encoded) > 2_000_000 or b'<!DOCTYPE' in encoded.upper() or b'<!ENTITY' in encoded.upper():
        raise ValueError('unsafe or oversized RSS')
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
    root = etree.fromstring(encoded, parser=parser)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('unsupported RSS document')
    out = []
    for entry in root.findall('./channel/item')[:limit]:
        title = entry.findtext('title') or ''
        if provider.startswith('google_') and ' - ' in title:
            title = title.rsplit(' - ', 1)[0]
        value = item(title, entry.findtext('description'), entry.findtext('link'),
                     published(entry.findtext('pubDate')), entry.findtext('source') or label,
                     provider=provider, source_url=source_url)
        if value is None:
            raise ValueError('RSS item lacks title and content')
        out.append(value)
    return out


def wallstreetcn(limit):
    from .news import item
    bounded_int(limit, 1, 50, 'limit')
    raw = read_json(WALLSTREETCN, {'channel': 'global-channel', 'limit': limit})
    rows = raw.get('data', {}).get('items') if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        raise ValueError('invalid WallStreetCN news response')
    out = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            raise ValueError('invalid WallStreetCN item')
        value = item(row.get('title'), row.get('content_text') or row.get('content'), row.get('uri'),
                     row.get('display_time'), '华尔街见闻', provider='wallstreetcn', source_url=WALLSTREETCN)
        if value is None:
            raise ValueError('WallStreetCN item lacks title and content')
        out.append(value)
    return out


def ithome(limit):
    bounded_int(limit, 1, 50, 'limit')
    return parse_rss(read(ITHOME), provider='ithome', source_url=ITHOME, label='IT之家', limit=limit)


def google(kind, limit):
    bounded_int(limit, 1, 50, 'limit')
    if kind not in GOOGLE_SITES:
        raise ValueError('unsupported Google News source')
    site, label = GOOGLE_SITES[kind]
    return parse_rss(read(GOOGLE, {'q': f'site:{site} when:1d', 'hl': 'zh-CN', 'gl': 'CN', 'ceid': 'CN:zh'}),
                     provider=f'google_{kind}', source_url=GOOGLE, label=label, limit=limit)


def raw_sources():
    return {'wallstreetcn': wallstreetcn, 'ithome': ithome,
            'google_36kr': partial(google, '36kr'), 'google_huxiu': partial(google, 'huxiu')}


def bounded_feed(name, limit):
    if name not in raw_sources():
        raise ValueError('unsupported extended source')
    bounded_int(limit, 1, 50, 'limit')
    result = subprocess.run([sys.executable, '-m', 'huohuo.market.news_feeds'],
                            input=json.dumps({'source': name, 'limit': limit}),
                            capture_output=True, text=True, timeout=8)
    if result.returncode or len(result.stdout) > 1_000_000:
        raise ValueError('extended news source unavailable')
    rows = json.loads(result.stdout)
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError('extended news response exceeds bound')
    return rows


def extended_sources():
    return {name: partial(bounded_feed, name) for name in raw_sources()}


def worker():
    # DNS 也可能阻塞；与外层 provider 的截止独立，失败只影响此来源。
    watchdog = threading.Timer(7, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        request = json.loads(sys.stdin.read(1000))
        if set(request) != {'source', 'limit'} or request['source'] not in raw_sources():
            raise ValueError('unsupported extended source request')
        rows = raw_sources()[request['source']](bounded_int(request['limit'], 1, 50, 'limit'))
        print(json.dumps(rows, ensure_ascii=False, allow_nan=False))
    finally:
        watchdog.cancel()


if __name__ == '__main__':
    worker()
