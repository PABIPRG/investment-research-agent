"""合成边界夹具；不读取用户实例或下载真实数据。"""
import json
import tempfile
from pathlib import Path
from huohuo.contracts import canonical
from huohuo.execution import Repository
from huohuo.industry_chain import IndustryChainService


def dataset(name='核心甲'):
    a = {'id': '600001', 'code': '600001', 'name': name, 'is_subject': True,
         'materials': [{'name': '材料甲', 'suppliers': [{'id': '600002', 'name': '供应乙', 'share': 0, 'type': 'direct'}]}],
         'products': [{'name': '产品甲', 'customers': [{'id': '600003', 'name': '客户丙', 'share': None, 'type': 'inferred', 'confidence': .8}]}]}
    b = {'id': '600002', 'code': '600002', 'name': '供应乙', 'materials': [], 'products': [{'name': '材料甲', 'customers': [{'id': '600001', 'name': name}]}]}
    return {'stats.json': {'companies': 2, 'total_nodes': 3, 'total_edges': 2},
        'companies.json': [{'code': '600001', 'name': name, 'is_subject': True}, {'code': '600002', 'name': '供应乙'}],
        'market-caps.json': {name: {'code': '600001', 'market_cap_cny': 100000000}},
        'view-data-all.json': {'companies': {'600001': a, '600002': b}},
        'network-data.json': {'nodes': [{'id': '600001', 'code': '600001', 'name': name, 'degree': 2}, {'id': '600002', 'code': '600002', 'name': '供应乙', 'degree': 1}, {'id': '600003', 'name': '客户丙', 'degree': 1}],
            'links': [{'source': '600002', 'target': '600001', 'kind': 'supplier', 'share': 0, 'type': 'direct'}, {'source': '600001', 'target': '600003', 'kind': 'customer', 'type': 'inferred', 'confidence': .8}]}}


class Response:
    def __init__(self, body, status=200, declared=None):
        self.body = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
        self.status_code = status
        self.headers = {'Content-Length': str(len(self.body) if declared is None else declared)}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size):
        for start in range(0, len(self.body), size): yield self.body[start:start+size]


class Source:
    def __init__(self, data=None):
        self.data, self.calls, self.failure = data or dataset(), [], None
    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.failure: raise self.failure
        return Response(self.data[url.rsplit('/', 1)[-1]])


class Fixture:
    def __init__(self, directory):
        self.root = Path(directory)
        self.repo = Repository(self.root / 'instance.sqlite3')
        schema = Path(__file__).parents[1] / 'sidecar/huohuo/industry_chain/014_industry_chain.sql'
        with self.repo.connection(True) as db:
            for statement in schema.read_text().split(';'):
                if statement.strip(): db.execute(statement)
            db.execute('CREATE TABLE research_tool_calls (id TEXT PRIMARY KEY, principal TEXT, session TEXT, tool_id TEXT, result TEXT)')
        self.source = Source()
        self.clock = 1000
        self.service = IndustryChainService(self.root / 'chain', self.repo, clock=lambda: self.clock, http_get=self.source)
        self.counter = 0
    def preview(self, action='bootstrap', payload=None, principal='p', session='s'):
        self.counter += 1
        if payload is None: payload = {'acknowledge_source_terms': True} if action in ('bootstrap', 'refresh') else {}
        return self.service.prepare(principal, session, {'request_key': str(self.counter), 'action': action, 'payload': payload})
    def commit(self, preview, principal='p', session='s'):
        return self.service.commit(principal, session, {key: preview[key] for key in ('preview_id', 'request_key')})
    def install(self): return self.commit(self.preview())
    def evidence(self, identifier='ev1', session='s', status='ok',code='600001'):
        with self.repo.connection(True) as db:
            db.execute('INSERT OR REPLACE INTO research_tool_calls VALUES(?,?,?,?,?)', (identifier, 'p', session, 'research_report_document_lookup', canonical({'status': status, 'source': 'https://example.invalid/report', 'data': {'document_role':'report_body','security_code':code,'document_sha256':'synthetic-hash','pages':[{'page':1,'text':'报告披露的合成关系'}]}})))


def overlay():
    return {'companies': [{'code': '600001', 'source_evidence_ids': ['ev1'], 'source_locations':[{'evidence_id':'ev1','page':1,'quote':'报告披露的合成关系'}], 'materials': [{'name': '新增材料', 'suppliers': [{'id': 'other', 'name': '新供应商', 'type': 'inferred', 'share': None, 'confidence': .6, 'note': '资料尚不能确认交易占比'}]}], 'products': [], 'related': [], 'metrics': []}], 'inferred_links': []}
