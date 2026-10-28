"""来源版本所有者；资料内容与事件原子保存，不从研究归档发事件。"""
import json
from datetime import datetime, timezone
from ..contracts import canonical, Invalid
from ..execution import digest, Conflict
from ..research_entities.bounded import collect, validate_financial_document
from ..contracts import scope as validate_scope
from ..market.source_transitions import record_source_transition
from ..research import snapshot
from .source_adapters import validate_quote_document, validate_profile_document, quote_session
from .models import EventEnvelope
from .router import EventRouter
from .market_sources import MARKET_OPERATIONS, HOOKS, collect_market, content_version, validate_market_document

HOOK = 'financial.summary_changed'
LEGACY_OPERATIONS={'financial_summary','company_profile','quote_snapshot'}
HOOKS={**HOOKS,'company_profile':'company.profile_changed','quote_snapshot':'quote.snapshot_changed'}
DISCOVERY_INTERVAL={'financial_summary':1800,'company_profile':21600,'quote_snapshot':900}

def trigger(scope, policy=None):
    if policy and policy.get('mode', 'condition') != 'condition': return []
    hook=HOOK if scope['operation']=='financial_summary' else HOOKS.get(scope['operation'])
    return [{'hook_type':hook,'scope_key':digest(scope)}] if hook else []

class Sources:
    def __init__(self, core): self.core=core; self.store=core.store

    def accept(self, principal, document):
        sc=document.get('scope',{})
        operation=sc.get('operation')
        if operation not in LEGACY_OPERATIONS | MARKET_OPERATIONS or document.get('status')!='ok':
            raise Invalid('仅接受已验证且成功的来源文档')
        sc=validate_scope(sc)
        if operation in MARKET_OPERATIONS:validate_market_document(document,sc)
        elif operation=='company_profile':validate_profile_document(document,sc)
        elif operation=='quote_snapshot':validate_quote_document(document,sc)
        else:validate_financial_document(document,sc)
        raw=document.get('raw')
        if operation=='financial_summary' and (not isinstance(raw,dict) or raw.get('code')!=sc['entity_id'].split(':')[-1]): raise Invalid('来源主体不匹配')
        if document.get('source_hash')!=digest(raw): raise Invalid('来源内容指纹不匹配')
        version=content_version(document) if operation in MARKET_OPERATIONS else digest(document['values']) if operation=='quote_snapshot' else digest(raw)
        key=digest(sc)
        now=datetime.now(timezone.utc)
        with self.store.transaction():
            db=self.store._connect()
            eid,changed=record_source_transition(db,principal=principal,scope_key=key,entity_id=sc['entity_id'],source=document['source'],version=version,document=document,observed_at=now.isoformat())
            if changed:self.store.record_event(EventEnvelope(event_id=eid,hook_type=HOOKS.get(operation,HOOK),producer='market-source' if operation in MARKET_OPERATIONS else 'financial-source',occurred_at=now,observed_at=now,source_version=version,content_hash=version,subject_ids=[sc['entity_id']],payload={'principal':principal,'scope_key':key,'version_kind':'content_hash','source_version':version}))
        return eid

    def catch_up(self, principal, mid):
        # 与创建/恢复的事务共享写锁，消除新订阅和来源入库之间的竞态。
        mandate=self.store.get_mandate_internal(mid)
        revision=self.store.get_revision(mid,mandate.current_revision)
        db=self.store._connect()
        # 恢复时比较最新可用版本，不把暂停期间的每个快照变成积压研究。
        for row in db.execute('SELECT event_id FROM source_heads WHERE principal=? AND scope_key=?',(principal,digest(revision.scope))):
            completed=db.execute("SELECT 1 FROM research_jobs WHERE mandate_id=? AND mandate_revision=? AND trigger_event_id=? AND status='completed'",(mid,mandate.current_revision,row[0])).fetchone()
            if not completed:self.core.event_router()._route_one(row[0])

    def discover(self, loader=None):
        # 仅一个到期来源；先持久占据时间槽，网络调用不占事务。异常可见且有退避。
        now=self.core.repo.clock()
        with self.store.transaction():
            db=self.store._connect()
            candidates=db.execute("SELECT DISTINCT m.principal_id,r.scope_json,r.contact_policy_json FROM mandates m JOIN mandate_revisions r ON r.mandate_id=m.mandate_id AND r.revision=m.current_revision WHERE m.status='tracking'").fetchall()
            selected=None
            for row in candidates:
                if json.loads(row['contact_policy_json']).get('mode', 'condition') != 'condition': continue
                sc=json.loads(row['scope_json'])
                if sc.get('operation') not in LEGACY_OPERATIONS | MARKET_OPERATIONS:continue
                key=digest(sc);old=db.execute('SELECT checked_at FROM source_checks WHERE principal=? AND scope_key=?',(row['principal_id'],key)).fetchone()
                interval=DISCOVERY_INTERVAL.get(sc['operation'],60 if sc['operation']=='market_quote' else 300)
                if sc['operation']=='quote_snapshot':
                    try:
                        if not quote_session(now,self.core.service.calendar):continue
                    except Exception:
                        db.execute("INSERT INTO source_checks VALUES(?,?,?,'unavailable','交易日历不可用，暂缓报价检查') ON CONFLICT(principal,scope_key) DO UPDATE SET checked_at=excluded.checked_at,status=excluded.status,detail=excluded.detail",(row['principal_id'],key,now))
                        continue
                if old and now-old[0]<interval:continue
                selected=(row['principal_id'],sc,key)
                db.execute("INSERT INTO source_checks VALUES(?,?,?,'collecting','正在读取来源') ON CONFLICT(principal,scope_key) DO UPDATE SET checked_at=excluded.checked_at,status=excluded.status,detail=excluded.detail",(row['principal_id'],key,now));break
        if selected is None:return {'checked':False}
        principal,sc,key=selected
        try:
            doc=loader(sc) if loader else collect_market(sc,self.core.market,self.core.service.calendar) if sc['operation'] in MARKET_OPERATIONS else snapshot(sc) if sc['operation']=='quote_snapshot' else collect(sc)
            if doc.get('scope') != sc:
                raise Invalid('来源没有返回本次请求的研究范围')
            if doc.get('status')=='ok':self.accept(principal,doc)
            status=doc.get('status','error');detail=doc.get('reason','来源内容版本已保存')
        except Exception:status='error';detail='资料采集或入库失败，稍后重试'
        with self.store.transaction():
            self.store._connect().execute('UPDATE source_checks SET status=?,detail=? WHERE principal=? AND scope_key=?',(status,detail,principal,key))
        return {'checked':True,'status':status}
