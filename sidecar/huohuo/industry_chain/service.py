"""当前实例产业链生命周期；程序拥有确认、版本、资料和审计回执。"""
import json
import threading
import time
import uuid
from copy import deepcopy
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, Missing, digest
from .seed import SeedData
from .seed_validation import SOURCE_URL, NOTICE
from .repository import GraphRepository
from .overlay import exact, validate_overlay, apply_overlay, code, sequence
from .universe_source import fetch_universe, URL as UNIVERSE_URL
from .query import query

LABELS = {'bootstrap': '下载产业链资料', 'refresh': '刷新产业链资料', 'delete': '删除产业链种子',
          'refresh_universe': '刷新 A 股基础清单', 'overlay': '保存研报产业链增量', 'clear_overlay': '移除研报产业链增量'}


class IndustryChainService:
    def __init__(self, root, repository, *, clock=time.time, http_get=None):
        self.repository, self.clock, self.http_get = repository, clock, http_get
        self.lock = threading.RLock()
        self.seed = SeedData(root, http_get=http_get, clock=clock, lock=self.lock)
        self.graph = GraphRepository(self.seed, self.lock)

    @staticmethod
    def _document(db, principal):
        row = db.execute('SELECT revision, document FROM industry_chain_state WHERE principal=?', (principal,)).fetchone()
        return (row['revision'], json.loads(row['document'])) if row else (0, {})

    def document(self, principal):
        with self.repository.connection() as db:
            return self._document(db, principal)

    def version(self, principal, db=None):
        revision, _ = self._document(db, principal) if db is not None else self.document(principal)
        return digest({'revision': revision, 'generation': self.seed.current().get('generation')})

    def status(self, principal, db=None):
        revision, document = self._document(db, principal) if db is not None else self.document(principal)
        state=self.seed.status()
        return {**state, 'basic_available':bool(state['available'] or document.get('universe') or document.get('companies')), 'overlay_revision': revision, 'overlay_companies': len(document.get('companies', {})),
                'inferred_links': len(document.get('inferred_links', [])), 'universe_companies': len(document.get('universe', [])),
                'universe_source': document.get('universe_source'), 'requires_confirmation': True}

    def query(self, principal, path, params=None):
        return query(self, principal, path, params)

    @staticmethod
    def preview_view(row):
        payload = json.loads(row['payload'])
        return {'preview_id': row['id'], 'request_key': row['request_key'], 'action': row['action'], 'summary': payload['summary'],
                'expires_at': row['expires_at'], 'status': row['status'], 'requires_confirmation': True,
                'source': NOTICE if row['action'] in ('bootstrap', 'refresh') else None}

    def sources(self, db, principal, session, payload):
        ids = {eid for item in payload['companies'] + payload['inferred_links'] for eid in item['source_evidence_ids']}
        sources = {}
        for eid in ids:
            row = db.execute('SELECT tool_id,result FROM research_tool_calls WHERE id=? AND principal=? AND session=?', (eid, principal, session)).fetchone()
            value = json.loads(row['result']) if row and row['result'] else None
            if not value or value.get('status') != 'ok':
                raise Invalid('产业链增量的资料证据必须来自本用户本会话成功的研究调用')
            body=value.get('data',{})
            pages=body.get('pages',[])
            if row['tool_id']!='research_report_document_lookup' or body.get('document_role')!='report_body' or not pages or not all(type(p.get('page')) is int and isinstance(p.get('text'),str) and p['text'].strip() for p in pages):
                raise Invalid('产业链关系须引用实际研报正文及页码；报价、评级、标题和盈利预测不能替代正文')
            codes={item['code'] for item in payload['companies'] if eid in item['source_evidence_ids']}
            if codes and codes!={body.get('security_code')}:raise Invalid('研报主体与待保存公司不一致，请按对应公司获取正文')
            citations=[]
            for item in payload['companies']+payload['inferred_links']:
                if eid not in item['source_evidence_ids']:continue
                if set(item['source_evidence_ids'])!={loc['evidence_id'] for loc in item['source_locations']}:
                    raise Invalid('每个引用证据都需要对应的正文定位，不能附加无定位证据')
                if 'source' in item and body.get('security_code') not in (item['source'],item['target']):raise Invalid('研报主体与推断关系两端均不一致')
                for loc in item['source_locations']:
                    if loc['evidence_id']!=eid:continue
                    page=next((p for p in pages if p['page']==loc['page']),None)
                    if page is None or ''.join(loc['quote'].split()) not in ''.join(page['text'].split()):
                        raise Invalid('引用页码或原文与实际读取的正文不一致')
                    citations.append(loc)
            sources[eid] = {'evidence_id': eid, 'tool_id': row['tool_id'], 'result_hash': digest(value), 'source': value.get('source'),
                            'document_role':'report_body','security_code':body.get('security_code'),'pages':[p['page'] for p in pages],'document_sha256':body.get('document_sha256'),'citations':citations}
        return sources

    def validate(self, action, payload):
        if action not in LABELS:
            raise Invalid('不支持的产业链操作')
        if action in ('bootstrap', 'refresh'):
            exact(payload, ('acknowledge_source_terms',))
            if payload['acknowledge_source_terms'] is not True:
                raise Invalid('下载前需要确认第三方资料的使用条件')
        elif action == 'overlay':
            return validate_overlay(payload)
        elif action == 'clear_overlay':
            exact(payload, ('codes',))
            sequence(payload['codes'], 100)
            if not payload['codes'] or len(set(payload['codes'])) != len(payload['codes']):
                raise Invalid('请选择要移除增量的公司')
            for item in payload['codes']:
                code(item)
        else:
            exact(payload, ())
        return deepcopy(payload)

    def prepare(self, principal, session, body):
        exact(body, ('request_key', 'action', 'payload'))
        text(principal, '用户', 200); text(session, '会话', 200); text(body['request_key'], '请求标识', 200)
        action, payload = body['action'], self.validate(body['action'], body['payload'])
        fingerprint = digest(body)
        with self.lock, self.repository.connection(True) as db:
            old = db.execute('SELECT * FROM industry_chain_previews WHERE principal=? AND session=? AND request_key=?', (principal, session, body['request_key'])).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise Conflict('同一请求标识不能更改产业链操作')
                return self.preview_view(old)
            sources = self.sources(db, principal, session, payload) if action == 'overlay' else {}
            summary = LABELS[action]
            if action in ('bootstrap', 'refresh'):
                summary += f'；来源 {SOURCE_URL}；固定 5 个 JSON，单文件最多 128 MiB、总量最多 256 MiB。'+NOTICE['notice']
            elif action == 'refresh_universe':
                summary += '；从东方财富公开接口读取当前证券清单、行业和市值，不构成完整产业链覆盖。'
            elif action == 'overlay':
                summary += f"；覆盖 {len(payload['companies'])} 家公司的研报增量、增加或更新 {len(payload['inferred_links'])} 条推断边；原始种子不改写。抽取候选不等于已核实的披露。"
            elif action == 'clear_overlay':
                summary += '；仅移除所选公司的增量和相关推断边，保留第三方种子。'
            else:
                summary += '；当前实例的第三方种子会删除，已保存研报增量和 A 股清单保留。'
            pid = 'ICV_' + uuid.uuid4().hex
            db.execute('INSERT INTO industry_chain_previews VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (pid, principal, session, body['request_key'], fingerprint, action, canonical({'command': payload, 'sources': sources, 'summary': summary}), self.version(principal, db), self.clock()+1800, 'pending', None))
            return self.preview_view(db.execute('SELECT * FROM industry_chain_previews WHERE id=?', (pid,)).fetchone())

    def commit(self, principal, session, body):
        exact(body, ('preview_id', 'request_key'))
        text(body['preview_id'], '确认凭证', 100); text(body['request_key'], '请求标识', 200)
        with self.lock, self.repository.connection(True) as db:
            row = db.execute('SELECT * FROM industry_chain_previews WHERE id=? AND principal=? AND session=?', (body['preview_id'], principal, session)).fetchone()
            if not row:
                raise Missing('产业链确认凭证不存在')
            if row['request_key'] != body['request_key']:
                raise Conflict('产业链请求标识不匹配')
            if row['result']:
                return json.loads(row['result'])
            if row['status'] != 'pending':
                raise Conflict('该操作已经开始或中断，请查询状态，不要重复提交')
            if row['expires_at'] < self.clock() or row['base_version'] != self.version(principal, db):
                raise Conflict('产业链预览已过期或数据版本已变化，请重新预览')
            if db.execute("SELECT 1 FROM industry_chain_previews WHERE status='running'").fetchone():
                raise Conflict('产业链有操作正在进行，请等待完成')
            db.execute("UPDATE industry_chain_previews SET status='running' WHERE id=?", (row['id'],))
            operation = dict(row)
        return self.execute(principal, session, operation)

    def execute(self, principal, session, operation):
        action, pid = operation['action'], operation['id']
        payload = json.loads(operation['payload'])
        command = payload['command']
        try:
            universe = None
            if action in ('bootstrap', 'refresh'):
                self.seed.download(pid, refresh=action == 'refresh')
            elif action == 'delete':
                self.seed.delete(pid)
            elif action == 'refresh_universe':
                universe = fetch_universe(self.http_get)
            with self.lock, self.repository.connection(True) as db:
                current = db.execute('SELECT status FROM industry_chain_previews WHERE id=?', (pid,)).fetchone()
                if current['status'] != 'running':
                    raise Conflict('产业链操作已失效，不能保存迟到结果')
                revision, document = self._document(db, principal)
                if action not in ('bootstrap', 'refresh', 'delete'):
                    if self.version(principal, db) != operation['base_version']:
                        raise Conflict('产业链数据已变化，本次结果未保存')
                    if action == 'overlay':
                        # 确认时重查证据，不能用被替换或失效的资料版本。
                        sources = self.sources(db, principal, session, command)
                        if sources != payload['sources']:
                            raise Conflict('产业链资料证据已变化，请重新预览')
                        document = apply_overlay(document, command, sources)
                    elif action == 'clear_overlay':
                        for code_ in command['codes']:
                            document.get('companies', {}).pop(code_, None)
                        document['inferred_links'] = [x for x in document.get('inferred_links', []) if x['source'] not in command['codes'] and x['target'] not in command['codes']]
                    else:
                        document['universe'] = universe
                        document['universe_source'] = {'url': UNIVERSE_URL, 'retrieved_at': self.clock(), 'count': len(universe), 'market_cap_unit': '亿元'}
                    db.execute('INSERT INTO industry_chain_state VALUES(?,?,?) ON CONFLICT(principal) DO UPDATE SET revision=excluded.revision, document=excluded.document', (principal, revision+1, canonical(document)))
                receipt = {'status': 'committed', 'action': action, 'preview_id': pid, 'data': self.status(principal, db)}
                db.execute("UPDATE industry_chain_previews SET status='committed',result=? WHERE id=?", (canonical(receipt), pid))
                return receipt
        except Exception as exc:
            receipt = {'status': 'failed', 'action': action, 'preview_id': pid, 'error': str(exc) if isinstance(exc, (Invalid, Conflict, ValueError)) else '来源请求或本地写入未完成，请核对状态后重新预览；不会自动重试'}
            with self.repository.connection(True) as db:
                db.execute("UPDATE industry_chain_previews SET status='failed',result=? WHERE id=? AND status='running'", (canonical(receipt), pid))
            return receipt

    def recovery(self):
        """仅进程启动恢复调用；不重放联网/写入，也不推断运行成功。"""
        with self.lock, self.repository.connection(True) as db:
            current = self.seed.current()
            for row in db.execute("SELECT * FROM industry_chain_previews WHERE status='running'").fetchall():
                published = row['action'] in ('bootstrap', 'refresh', 'delete') and current.get('operation_id') == row['id']
                receipt = {'status': 'committed' if published else 'interrupted', 'action': row['action'], 'preview_id': row['id'],
                           'message': '已从原子发布记录恢复' if published else '进程中断，本次操作未确认完成；请核对后重新预览，不会自动重试', 'data': self.status(row['principal'], db)}
                db.execute('UPDATE industry_chain_previews SET status=?,result=? WHERE id=?', (receipt['status'], canonical(receipt), row['id']))
