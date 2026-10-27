"""来源版本所有者；资料内容与事件原子保存，不从研究归档发事件。"""
import json
from datetime import datetime, timezone
from ..contracts import canonical, Invalid
from ..execution import digest, Conflict
from ..research_entities.bounded import collect, validate_financial_document
from ..research import snapshot
from ..contracts import scope as validate_scope
from .models import EventEnvelope
from .router import EventRouter

HOOK = 'financial.summary_changed'
PROFILE_HOOK = 'company.profile_changed'
QUOTE_HOOK = 'quote.snapshot_changed'
_PROFILE_SOURCE = 'akshare.stock_profile_cninfo'
_PROFILE_URL = 'https://webapi.cninfo.com.cn/'
_QUOTE_SOURCE = 'eastmoney'
_QUOTE_UNITS = {'price': 'CNY/share', 'change': 'CNY', 'change_percent': '%'}
# 公司资料变化很慢，避免与财务摘要共用 30 分钟轮询；报价只在交易时段每 15 分钟检查。
DISCOVERY_INTERVAL = {'financial_summary': 1800, 'company_profile': 21600, 'quote_snapshot': 900}
QUOTE_SESSION_MINUTES = ((9 * 60 + 30, 11 * 60 + 30), (13 * 60, 15 * 60))

def in_quote_session(now):
    """沪深交易时段（工作日 09:30–11:30、13:00–15:00），节假日没有交易所日历时照常检查。"""
    from zoneinfo import ZoneInfo
    local =datetime.fromtimestamp(now, timezone.utc).astimezone(ZoneInfo('Asia/Shanghai'))
    if local.weekday() >= 5:
        return False
    minute = local.hour * 60 + local.minute
    return any(start <= minute < end for start, end in QUOTE_SESSION_MINUTES)

def trigger(scope):
    operation = scope['operation']
    if operation == 'financial_summary':
        return [{'hook_type': HOOK, 'scope_key': digest(scope)}]
    if operation == 'company_profile':
        return [{'hook_type': PROFILE_HOOK, 'scope_key': digest(scope)}]
    if operation == 'quote_snapshot':
        return [{'hook_type': QUOTE_HOOK, 'scope_key': digest(scope)}]
    return []

def validate_quote_document(document, binding):
    """报价同样只接受与本次范围、主体和内容指纹一致的快照。"""
    if document.get('scope') != binding:
        raise Invalid('quote evidence scope mismatch')
    raw = document.get('raw')
    if not isinstance(raw, dict):
        raise Invalid('quote evidence raw missing')
    if document.get('source_hash') != digest(raw):
        raise Invalid('quote evidence source hash mismatch')
    values = document.get('values')
    if not isinstance(values, dict):
        raise Invalid('quote evidence values missing')
    for field, unit in _QUOTE_UNITS.items():
        try:
            number = float(values[field])
        except (KeyError, TypeError, ValueError):
            raise Invalid('quote evidence values invalid') from None
        if not number == number or number in (float('inf'), float('-inf')):
            raise Invalid('quote evidence values invalid')
    if values.get('price_unit') != 'CNY/share' or values.get('currency') != 'CNY':
        raise Invalid('quote evidence unit mismatch')
    if document.get('source') != _QUOTE_SOURCE:
        raise Invalid('quote evidence source mismatch')
    try:
        observed = datetime.fromisoformat(document.get('observed_at', ''))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise Invalid('quote evidence observation time missing') from None

def validate_profile_document(document, binding):
    """公司资料同样只接受与本次范围、主体和内容指纹一致的来源文档。"""
    if document.get('scope') != binding:
        raise Invalid('profile evidence scope mismatch')
    raw = document.get('raw')
    if not isinstance(raw, dict) or raw.get('code') != binding['entity_id'].split(':')[-1]:
        raise Invalid('profile evidence subject mismatch')
    if document.get('source_hash') != digest(raw):
        raise Invalid('profile evidence source hash mismatch')
    rows = raw.get('records')
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise Invalid('profile evidence schema invalid')
    if document.get('values') != {'code': raw['code'], 'profile': rows[:1]}:
        raise Invalid('profile evidence semantics mismatch')
    if document.get('source') != _PROFILE_SOURCE or document.get('source_url') != _PROFILE_URL:
        raise Invalid('profile evidence source mismatch')
    try:
        observed = datetime.fromisoformat(document.get('observed_at', ''))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise Invalid('profile evidence observation time missing') from None

class Sources:
    def __init__(self, core): self.core=core; self.store=core.store

    def accept(self, principal, document):
        sc=document.get('scope',{})
        operation=sc.get('operation')
        if operation not in DISCOVERY_INTERVAL or document.get('status')!='ok':
            raise Invalid('仅接受成功的财务摘要、公司资料或报价来源文档')
        binding=validate_scope(sc)
        if operation=='financial_summary': validate_financial_document(document, binding)
        elif operation=='company_profile': validate_profile_document(document, binding)
        else: validate_quote_document(document, binding)
        raw=document.get('raw')
        if operation=='quote_snapshot':
            # 报价按价格字段取版本：抓取时间变化不算新内容，避免每次轮询都产生事件。
            version=digest(document['values'])
        else:
            version=digest(raw)
            if document.get('source_hash')!=version: raise Invalid('来源内容指纹不匹配')
        hook={'financial_summary':HOOK,'company_profile':PROFILE_HOOK}.get(operation,QUOTE_HOOK)
        producer={'financial_summary':'financial-source','company_profile':'profile-source'}.get(operation,'market-source')
        key=digest(sc); eid='SRC_'+digest([principal,key,document['source'],version])
        now=datetime.now(timezone.utc)
        with self.store.transaction():
            db=self.store._connect()
            db.execute('INSERT OR IGNORE INTO source_versions VALUES(?,?,?,?,?,?,?,?)',(eid,principal,sc['entity_id'],key,document['source'],version,canonical(document),now.isoformat()))
            self.store.record_event(EventEnvelope(event_id=eid,hook_type=hook,producer=producer,occurred_at=now,observed_at=now,source_version=version,content_hash=version,subject_ids=[sc['entity_id']],payload={'principal':principal,'scope_key':key,'version_kind':'content_hash','source_version':version}))
        return eid

    def catch_up(self, principal, mid):
        # 与创建/恢复的事务共享写锁，消除新订阅和来源入库之间的竞态。
        mandate=self.store.get_mandate_internal(mid)
        revision=self.store.get_revision(mid,mandate.current_revision)
        for row in self.store._connect().execute('SELECT event_id FROM source_versions WHERE principal=? AND scope_key=?',(principal,digest(revision.scope))):
            EventRouter(self.store)._route_one(row[0])

    def discover(self, loader=None):
        # 仅一个到期来源；先持久占据时间槽，网络调用不占事务。异常可见且有退避。
        now=self.core.repo.clock()
        with self.store.transaction():
            db=self.store._connect()
            candidates=db.execute("SELECT DISTINCT m.principal_id,r.scope_json FROM mandates m JOIN mandate_revisions r ON r.mandate_id=m.mandate_id AND r.revision=m.current_revision WHERE m.status='tracking'").fetchall()
            selected=None
            for row in candidates:
                sc=json.loads(row['scope_json'])
                interval=DISCOVERY_INTERVAL.get(sc.get('operation'))
                if interval is None:continue
                # 报价只在交易时段检查；节假日没有交易所日历，照常轮询但内容不变不会产生事件。
                if sc.get('operation')=='quote_snapshot' and not in_quote_session(now):continue
                key=digest(sc);old=db.execute('SELECT checked_at FROM source_checks WHERE principal=? AND scope_key=?',(row['principal_id'],key)).fetchone()
                if old and now-old[0]<interval:continue
                selected=(row['principal_id'],sc,key)
                db.execute("INSERT INTO source_checks VALUES(?,?,?,'collecting','正在读取来源') ON CONFLICT(principal,scope_key) DO UPDATE SET checked_at=excluded.checked_at,status=excluded.status,detail=excluded.detail",(row['principal_id'],key,now));break
        if selected is None:return {'checked':False}
        principal,sc,key=selected
        collector=loader or (snapshot if sc.get('operation')=='quote_snapshot' else collect)
        try:
            doc=collector(sc)
            if doc.get('scope') != sc:
                raise Invalid('来源没有返回本次请求的研究范围')
            if doc.get('status')=='ok':self.accept(principal,doc)
            status=doc.get('status','error');detail=doc.get('reason','来源内容版本已保存')
        except Exception:status='error';detail='资料采集或入库失败，稍后重试'
        with self.store.transaction():
            self.store._connect().execute('UPDATE source_checks SET status=?,detail=? WHERE principal=? AND scope_key=?',(status,detail,principal,key))
        return {'checked':True,'status':status}
