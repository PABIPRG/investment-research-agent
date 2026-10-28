"""显式请求时读取固定公开 A 股清单；不接旧服务、不使用模型。"""
import json
import requests
from .overlay import number, code

URL = 'https://push2delay.eastmoney.com/api/qt/clist/get'
MAX_BYTES = 12 * 1024 * 1024
MAX_PAGES = 100


def fetch_universe(http_get=None):
    get = http_get or requests.get
    result, consumed, seen = [], 0, set()
    total = None
    for page in range(1, MAX_PAGES + 1):
        params = {'pn': page, 'pz': 100, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2, 'fid': 'f12',
                  'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
                  'fields': 'f12,f14,f20,f100'}
        with get(URL, params=params, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}, timeout=(5, 20), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError('A 股清单来源暂不可用')
            chunks = []
            for chunk in response.iter_content(65536):
                consumed += len(chunk)
                if consumed > MAX_BYTES:
                    raise ValueError('A 股清单超过大小限制')
                chunks.append(chunk)
            body = json.loads(b''.join(chunks))
        data = body.get('data') or {}
        count = data.get('total')
        if not isinstance(count, int) or isinstance(count, bool) or not 0 < count <= 10000:
            raise ValueError('A 股清单数量无效')
        if total is not None and count != total:
            raise ValueError('清单在分页期间改变，请重新确认刷新')
        total = count
        rows = data.get('diff')
        if not isinstance(rows, list) or not rows:
            raise ValueError('A 股清单分页不完整')
        for row in rows:
            symbol = code(row.get('f12'))
            if symbol in seen or not isinstance(row.get('f14'), str) or not row['f14'].strip():
                raise ValueError('A 股清单存在重复或无效证券')
            seen.add(symbol)
            cap = row.get('f20')
            if cap in ('-', None):
                cap = None
            else:
                cap = number(cap, 0, 1e16) / 1e8
            industry = row.get('f100')
            result.append({'code': symbol, 'name': row['f14'], 'industry': industry if isinstance(industry, str) else '',
                           'market_cap': cap, 'board': '北交所' if symbol[0] in '489' else '科创板' if symbol.startswith('688') else '创业板' if symbol.startswith('30') else '主板'})
        if len(result) >= total:
            if len(result) != total:
                raise ValueError('A 股清单数量与来源不符')
            return result
    raise ValueError('A 股清单分页超过上限')
