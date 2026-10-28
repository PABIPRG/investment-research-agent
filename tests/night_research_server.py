"""仅本任务隔离 UAT：真实 API/SQLite，目录和资料明确合成。"""
import json
import sys
import threading
from pathlib import Path
from huohuo import server as api
from huohuo.research_entities.bounded import collect

config = json.loads(Path(sys.argv[1]).read_text())

def fixture(scope):
    value = '' if scope.get('metric') == '净利润' else 123
    document = collect(scope, lambda _: {'code': scope['entity_id'].split(':')[-1],
        'records': [{'指标': scope['metric'], scope['period']: value}]})
    document['limitations'].append('明确合成验收资料；不代表真实财务披露。')
    return document

# UI search shares the real endpoint while this isolated server stays synthetic.
from huohuo.research_entities.security_search import search

def fixture_search(query):
    result = search(query, loader=lambda: [
        {'code': '600519', 'name': '贵州茅台'},
        {'code': '000001', 'name': '平安银行'},
    ])
    result['source'] = {'provider': '明确合成 UI 验收目录'}
    return result

api.search_securities = fixture_search
api.collect = fixture
with api.Service(config) as service:
    service.mandates.entities.directory = lambda: {'status': 'ok', 'rows': [
        {'code': '600519', 'name': '贵州茅台'}], 'source': {'provider': '明确合成目录'}}
    discover = service.mandates.sources.discover
    service.mandates.sources.discover = lambda: discover(loader=fixture)
    def lifetime():
        sys.stdin.buffer.read()
        service.shutdown()
    threading.Thread(target=lifetime, daemon=True).start()
    print('ready', flush=True)
    service.serve_forever(poll_interval=.1)
