"""聊天工具桥：确认身份由程序绑定，采集在事务外执行，证据按会话持久化。"""
import json
from urllib.parse import urlsplit
from .adapters.storage_memory import InMemoryEntityRepository
from .models import EntityInstance
from .resolution import DirectoryRepository
from .security_search import search as search_securities
from .registry.tools import TOOL_REGISTRY
from .tool_contracts import validate_args
from .toolbox.context import ToolContext, ToolUnavailable
from .toolbox.contracts import ToolRequest
from .toolbox.executor import ToolExecutor
from .toolbox.cache import TTLCache
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, digest


class IsolatedToolContext(ToolContext):
    """不继承旧应用服务地址，也不自动操作监控或读取旧账户。"""
    def __init__(self, repository):
        super().__init__(repository, industry_chain_url='http://127.0.0.1:1',
                         market_watch_url='http://127.0.0.1:1', evolution_url='http://127.0.0.1:1')
    def http_get(self, url, params=None):
        parsed = urlsplit(url)
        local = getattr(self, 'industry_chain_query', None)
        if local and parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:1' and not parsed.query and not parsed.fragment and (parsed.path in ('/data/status', '/stats', '/companies', '/graph/network') or parsed.path.startswith(('/companies/', '/graph/entity/', '/graph/single/', '/graph/chain/'))):
            return local(parsed.path, params)
        if parsed.hostname in ('127.0.0.1','localhost','::1'):
            raise ToolUnavailable('独立实例尚未配置此服务依赖；未探测其他本地服务')
        return super().http_get(url,params)
    def http_post(self, url, payload):
        raise ToolUnavailable('当前研究工具桥不执行外部写操作')


class ResearchToolBridge:
    def __init__(self, repo, confirmations, context_factory=IsolatedToolContext, strategies=None):
        self.repo,self.confirmations,self.context_factory=repo,confirmations,context_factory
        self.strategies = strategies
        self.industry_chain = None

    def run(self, principal, session, call_id, tool_id, arguments):
        text(session,'session',200);text(call_id,'call_id',200)
        args=validate_args(tool_id,arguments)
        key=digest([principal,session,call_id,tool_id]);fingerprint=digest(args)
        # 同一调用重放返回已留存结果；中断调用不悄悄重新采集。
        with self.repo.connection() as db:
            prior=db.execute('SELECT fingerprint,result FROM research_tool_calls WHERE id=?',(key,)).fetchone()
        if prior:
            if prior['fingerprint']!=fingerprint:raise Conflict('同一工具调用不可更改参数')
            return json.loads(prior['result']) if prior['result'] else {'status':'unavailable','error':'调用未完成，请检查后明确重试','evidence_id':key}
        repository=InMemoryEntityRepository()
        repository.upsert_entities(DirectoryRepository([]).entities.values(), source_version="bundled")
        entities=[]
        cid=args.pop('confirmation_id',None)
        if cid:
            current=next((c for c in self.confirmations.current(principal,session) if c['confirmation_id']==cid),None)
            if not current:raise Invalid('需要本对话有效的实体确认')
            self.confirmations.validate(principal,session,cid,current['entity_id'])
            definition=TOOL_REGISTRY[tool_id]
            if definition.supported_entity_types and current['entity_type_code'] not in definition.supported_entity_types:
                raise Invalid('工具不支持已确认的实体类型')
            entity=repository.get(current['entity_id'])
            if entity is None:
                identifiers=dict(current.get('identifiers',{}))
                if current['entity_id'].startswith(('SEC:CN:A:','CO:CN:A:')):
                    identifiers={'security_code':current['entity_id'].rsplit(':',1)[-1],'company_code':current['entity_id'].rsplit(':',1)[-1]}
                entity=EntityInstance(entity_id=current['entity_id'],entity_type_code=current['entity_type_code'],
                                      canonical_name=current['label'],identifiers=identifiers,attributes=current.get('attributes',{}),source='本会话用户确认的目录候选')
                repository.upsert_entities([entity], source_version="confirmed")
            entities=[entity.entity_id]
        with self.repo.connection(True) as db:
            # 并发重复调用也必须先查回执，不能重复触发外部采集。
            prior=db.execute('SELECT fingerprint,result FROM research_tool_calls WHERE id=?',(key,)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:raise Conflict('同一工具调用不可更改参数')
                return json.loads(prior['result']) if prior['result'] else {'status':'unavailable','error':'调用尚未完成','evidence_id':key}
            count=db.execute('SELECT COUNT(*) FROM research_tool_calls WHERE principal=? AND session=? AND created_at>?',
                             (principal,session,self.repo.clock()-60)).fetchone()[0]
            if count>=20:raise Invalid('本对话每分钟最多执行 20 次研究工具，请稍后再试')
            db.execute('INSERT INTO research_tool_calls VALUES(?,?,?,?,?,?,?,?,?)',
                       (key,principal,session,call_id,tool_id,fingerprint,canonical(arguments),None,self.repo.clock()))
        definition=TOOL_REGISTRY[tool_id]
        discovery_failure=None
        if tool_id=='security_lookup':
            found=search_securities(args.get('code') or args.get('name'))
            if found['status']=='ok':
                repository.upsert_entities(DirectoryRepository(found['candidates']).entities.values(),source_version='public-directory')
            elif found['status'] not in ('ok','empty'):
                discovery_failure={'tool_id':tool_id,'status':'unavailable','data':{},'error':'证券目录不可用，不能将失败当作未找到对象','source':found.get('source')}
        if discovery_failure is not None:
            result=discovery_failure
        elif definition.requires_authorization or tool_id=='event_monitor_setup':
            result={'tool_id':tool_id,'status':'needs_authorization','data':{},'error':'此能力尚未接通独立实例的授权流程，未执行操作'}
        else:
            context=self.context_factory(repository)
            if self.strategies is not None:
                def query_strategy(path,params):
                    from ..execution import Missing
                    try:
                        view=self.strategies.read(principal,params.get("strategy_id"))
                        return view[{"/evolution/status":"pool","/evolution/attribution":"attribution","/evolution/preview":"preview"}[path]]
                    except (Missing,Invalid) as exc:raise ToolUnavailable(str(exc)) from exc
                context.evolution_query=query_strategy
            if self.industry_chain is not None:
                context.industry_chain_query = lambda path, params=None: self.industry_chain.query(principal, path, params)
            executor=ToolExecutor(context,audit=False,persist_evidence=False,cache=TTLCache())
            result=executor.execute(ToolRequest(tool_id=tool_id,entity_ids=entities,params=args,request_id=key,authorized=False)).model_dump(mode='json')
        result.update(evidence_id=key,request_id=key)
        encoded=canonical(result)
        if len(encoded.encode())>100_000:
            result={'tool_id':tool_id,'status':'unavailable','evidence_id':key,'error':'结果超过实例证据大小上限，请缩小 limit 或时间范围'}
            encoded=canonical(result)
        with self.repo.connection(True) as db:db.execute('UPDATE research_tool_calls SET result=? WHERE id=?',(encoded,key))
        return result

    def evidence(self,principal,session,evidence_id):
        with self.repo.connection() as db:
            row=db.execute('SELECT result FROM research_tool_calls WHERE id=? AND principal=? AND session=?',(evidence_id,principal,session)).fetchone()
        if not row:raise Invalid('证据不存在或不属于当前对话')
        return json.loads(row['result']) if row['result'] else {'status':'unavailable','error':'调用尚无结果'}
