"""策略约定内的新闻来源；复用市场适配器，证据与事件保持稳定。"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from ..contracts import Invalid, canonical
from ..execution import digest


def source(market, repository, principal):
    def collect(securities):
        events = []
        pool = ThreadPoolExecutor(max_workers=4)
        futures = [(security, pool.submit(market.query, {'operation':'news','code':security['code'],'limit':5})) for security in securities]
        deadline = time.monotonic()+90
        try:
            responses = [(security, future.result(timeout=max(.01,deadline-time.monotonic()))) for security,future in futures]
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        for security, response in responses:
            if response.get('status') not in {'ok','empty'} or response.get('stale') is not False or response.get('complete') is not True:
                raise Invalid('策略新闻来源失败、陈旧或时间未知，本次未生成事件候选')
            now = repository.clock()
            for item in response['data'].get('items', []):
                try: published = datetime.fromisoformat(item['published_at']).timestamp()
                except (ValueError, TypeError, KeyError): raise Invalid('策略新闻发布时间无法核对') from None
                if published > now + 60 or published < now - 86400:
                    continue
                eid = 'market-news:' + digest([security['code'], item['id'], item['content']])
                with repository.connection() as db:
                    old = db.execute('SELECT document FROM strategy_events WHERE principal=? AND id=?',(principal,eid)).fetchone()
                if old:
                    # 反复采集不改变事件身份、内容或首次观察时间。
                    events.append(json.loads(old[0])); continue
                evidence = (item.get('url') or item.get('source_url') or 'market-news:'+digest(item))[:300]
                events.append({'id':eid,'source':str(item.get('source') or response['source'])[:200], 'observed_at':now,
                    'title':item['title'][:300], 'summary':item['content'][:3900]+'；按代码检索的相关文章，相关性须核对，不代表公司正式披露。',
                    'securities':[security], 'evidence_ref':evidence})
        return events
    return collect
