"""迁移组合 UAT：真实 API/SQLite/DSH，全部公开资料由明确合成夹具替代。"""
import json
import sys
import threading
import time
from urllib.parse import urlsplit
from pathlib import Path
from huohuo import server as api
from huohuo.research_entities.security_search import search
from huohuo.research_entities.bounded import collect
from test_industry_chain_fixtures import Source
from test_strategy_domain import bars
from migration_market_fixture import MigrationMarket, ROWS

config = json.loads(Path(sys.argv[1]).read_text())
rows = ROWS
api.search_securities = lambda q: search(q, loader=lambda: rows)
api.collect = lambda scope: collect(scope, lambda _: {'code': scope['entity_id'].split(':')[-1],
    'records': [{'指标': scope.get('metric', '营业总收入'), scope.get('period', '2026-06-30'): 123}]})

market = MigrationMarket(Path(config['workspace']) / 'migration-market.json')

def history(code, start, end):
    return {'records': [x for x in bars(count=1000) if start <= x['date'] <= end],
            'source': 'synthetic:migration-ui', 'adjustment': 'qfq'}

with api.Service(config) as service:
    # Optional controls live only in this isolated UAT fixture, never in product routes.
    class ControlledReads(api.Handler):
        def handle_request(self):
            path=urlsplit(self.path).path
            if self.command=='GET' and path in {'/mandates','/strategies','/executions','/notifications/config','/notifications'}:
                try:control=json.loads((Path(config['workspace'])/'ui-read-control.json').read_text())
                except (FileNotFoundError,ValueError):control={}
                if path in control.get('paths',[]):
                    time.sleep(max(0,min(3,float(control.get('delay',0)))))
                    if control.get('fail'):
                        return self.reply(503,{'detail':'合成验收：暂时无法读取，请重试。'})
            return super().handle_request()
    service.RequestHandlerClass=ControlledReads
    class SyntheticNotificationAdapter:
        def send(self,job):
            control=Path(config['workspace'])/'notification-test-control.json'
            try:mode=json.loads(control.read_text())
            except (FileNotFoundError,ValueError):mode={}
            with (Path(config['workspace'])/'notification-transport-proof.jsonl').open('a') as proof:
                proof.write(json.dumps({'synthetic':True,'title':job['title'],'content':job['content']},ensure_ascii=False)+'\n')
            if mode.get('delay'):time.sleep(min(3,float(mode['delay'])))
            if mode.get('unknown'):raise RuntimeError('synthetic transport uncertainty')
            return None
    service.mandates.notifications.adapters={c:SyntheticNotificationAdapter() for c in ('wecom','serverchan','email')}
    service.mandates.entities.directory = lambda: {'status': 'ok', 'rows': rows, 'source': {'provider': '明确合成目录'}}
    service.market.provider = market.query
    service.strategies.history = history
    service.calendar.refresh = lambda: None
    service.calendar.is_trading_day = lambda day: day.weekday() < 5
    service.industry_chain.seed.http_get = Source()
    discover = service.mandates.sources.discover
    from huohuo.research_partner.market_sources import collect_market, MARKET_OPERATIONS
    service.mandates.sources.discover = lambda: discover(loader=lambda scope:
        collect_market(scope, service.market, service.calendar) if scope['operation'] in MARKET_OPERATIONS else api.collect(scope))
    def lifetime():
        sys.stdin.buffer.read()
        service.shutdown()
    threading.Thread(target=lifetime, daemon=True).start()
    print('ready', flush=True)
    service.serve_forever(poll_interval=.1)
