"""委托上下文绑定；不扩大已有单证券执行 Scope。"""
import json
from ..contracts import Invalid,canonical,text
from ..execution import Conflict,digest
from ..research_partner.commands import MandateReviseRequest
from ..research_partner.models import EventEnvelope
from .collections import CollectionProvider

class InvestmentBinding:
    def __init__(self,core,investment):self.core,self.investment,self.store=core,investment,core.store
    def get(self,principal,mid):
        row=self.store._connect().execute('SELECT * FROM investment_collections WHERE principal=? AND mandate_id=?',(principal,mid)).fetchone()
        if not row:return None
        return {'collection':row['collection'],'mode':row['mode'],'bound_version':row['bound_version'],'members':json.loads(row['members']),'role':'research_context','execution_limit':'当前仍按委托明确证券执行，不自动展开为多证券研究。'}
    def bind(self,principal,body):
        if set(body)!={'mandate_id','collection','mode','expected_revision','expected_generation','expected_fact_version','request_key'}:raise Invalid('集合绑定字段无效')
        if body['mode'] not in ('fixed','dynamic'):raise Invalid('请选择固定或动态范围')
        key=text(body['request_key'],'请求标识',200);fingerprint=digest(body);mid=body['mandate_id']
        with self.store.transaction():
            db=self.store._connect()
            old=db.execute('SELECT * FROM investment_receipts WHERE principal=? AND request_key=?',(principal,key)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise Conflict('请求标识冲突')
                return json.loads(old['receipt'])
            view=self.core.get(principal,mid)
            if view['mandate']['status']=='ended':raise Invalid('已结束委托不能绑定集合')
            if body['expected_revision']!=view['mandate']['current_revision'] or body['expected_generation']!=view['generation']:raise Conflict('委托版本已变化，请刷新')
            snap=CollectionProvider(self.investment,principal).read_snapshot(body['collection'])
            if snap['fact_version']!=body['expected_fact_version']:raise Conflict('投资事实已变化，请刷新')
            if snap['status']=='not_recorded':raise Invalid('尚未录入投资事实，不能将其当作空集合')
            revision=view['revision'];basis=dict(revision['basis']);basis['investment_collection']={'collection':body['collection'],'mode':body['mode'],'fact_version':snap['fact_version'],'members':snap['members'],'role':'research_context'}
            # 明确用户绑定才新增事实依赖；自选写入本身不产生任何委托。
            triggers=[x for x in revision.get('triggers',[]) if x.get('hook_type')!='investment.facts_revised']
            triggers.append({'hook_type':'investment.facts_revised','subject_ids':[] if body['mode']=='dynamic' else [x['entity_id'] for x in snap['members']]})
            self.core.service.revise(self.core.context(principal),mid,MandateReviseRequest(goal=revision['goal'],scope=revision['scope'],subjects=revision.get('subjects') or [{'entity_id':revision['scope']['entity_id']}],triggers=triggers,contact_policy=revision.get('contact_policy',{}),basis=basis,expected_revision=body['expected_revision'],idempotency_key=key))
            db.execute('INSERT INTO investment_collections VALUES(?,?,?,?,?,?) ON CONFLICT(principal,mandate_id) DO UPDATE SET collection=excluded.collection,mode=excluded.mode,bound_version=excluded.bound_version,members=excluded.members',(principal,mid,body['collection'],body['mode'],snap['fact_version'],canonical(snap['members'])))
            db.execute('UPDATE mandate_generation SET generation=generation+1 WHERE mandate_id=?',(mid,))
            db.execute("UPDATE attempts SET status='cancelled' WHERE status='running' AND execution_id IN (SELECT execution_id FROM execution_jobs WHERE mandate_id=?)",(mid,))
            db.execute("UPDATE executions SET status='cancelled',revision=revision+1 WHERE status IN ('queued','running') AND id IN (SELECT execution_id FROM execution_jobs WHERE mandate_id=?)",(mid,))
            db.execute("UPDATE research_jobs SET status='cancelled' WHERE mandate_id=? AND status IN ('pending','running','waiting_data')",(mid,))
            result=self.core.get(principal,mid)
            db.execute('INSERT INTO investment_receipts VALUES(?,?,?,?)',(principal,key,fingerprint,canonical(result)))
            return result
    def capture(self,principal,mid,execution_id):
        db=self.store._connect();binding=self.get(principal,mid)
        if binding:
            snap=CollectionProvider(self.investment,principal).read_snapshot(binding['collection'],binding['bound_version'] if binding['mode']=='fixed' else None)
            version=snap['fact_version'];members=snap['members'];collection=binding['collection'];mode=binding['mode']
        else:
            version=self.investment.read(principal)['version'];members=[];collection=mode=None
        db.execute('INSERT INTO investment_run_facts VALUES(?,?,?,?,?,?)',(principal,execution_id,version,collection,mode,canonical(members)))
        return str(version)
    def publish(self):
        # 投资 outbox 与核心 inbox 同库，同事务交接；稳定 event_id 支持幂等重放。
        db=self.store._connect()
        for row in db.execute('SELECT * FROM investment_outbox WHERE published=0').fetchall():
            self.store.record_event(EventEnvelope(**json.loads(row['envelope'])))
            db.execute('UPDATE investment_outbox SET published=1 WHERE event_id=?',(row['event_id'],))
