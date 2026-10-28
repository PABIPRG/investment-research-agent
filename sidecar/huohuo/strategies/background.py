"""策略计算适配器：任务、租约和恢复全部来自委托核心。"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from ..execution import Conflict
from .storage import Documents
from .legacy import evolution
from .legacy.runtime import runtime
from .workflow import execute
from . import schedule


def recover(service):
    service.tasks.repo.recover()
    with service.store.transaction(): service.tasks.route()


def _eligible(service, docs, action, sid, policy):
    if action in ('events','recall'): return None
    value = docs.get('strategies',sid)
    if not value or value.get('status') in ('retired','rejected') or (value.get('evolve') or {}).get('state')=='retired': return '策略已停止或不在验证状态'
    if action=='shadow' and value['status']!='active': return '尚未完成有效回测'
    last=(value.get('backtest') or {}).get('ran_at')
    if action=='backtest' and last and service.clock()-datetime.fromisoformat(last).timestamp()<policy['retest_days']*86400: return '尚未到约定的回测间隔'
    return None


def run(service, principal, jid, token):
    tasks=service.tasks; db=service.store._connect(); docs=Documents(service.store,principal)
    with service.store.transaction(), runtime(service.clock):
        bound=tasks.bound(principal,jid,token,terminal=True)
        if bound['result_hash']: return json.loads(bound['result'])['strategy_receipt']
        scope=json.loads(bound['scope']); action=scope['action']
        if action=='candidate': raise Conflict('候选任务必须由受限 DSH 执行')
        policy=schedule.assert_active(service,principal,scope['revision'])
        job=service.store.get_job(jid); payload=dict(job.checkpoint); sid=payload['strategy_id']
        existing=db.execute('SELECT id FROM strategy_runs WHERE execution_id=?',(bound['id'],)).fetchone()
        if existing: raise Conflict('本次计算已经开始；不得重复执行')
        run_id='SRN_'+uuid.uuid4().hex; version=docs.version(); at=service.clock()
        db.execute('INSERT INTO strategy_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,principal,sid,jid,action,'running',at,at,version,None,None,bound['id']))
        db.execute('INSERT INTO strategy_run_subjects VALUES(?,?,?)',(run_id,principal,sid))
        reason=_eligible(service,docs,action,sid,policy)
        if reason:
            db.execute("UPDATE strategy_runs SET status='skipped',error=? WHERE id=?",(reason,run_id))
            receipt={'run':service.run_view(db.execute('SELECT * FROM strategy_runs WHERE id=?',(run_id,)).fetchone()),'note':reason}
            tasks.complete(principal,jid,token,receipt); _close_batch(service,docs,job)
            return receipt
        if action=='events':
            from .event_sources import scope as event_scope
            payload['securities']=event_scope(docs,policy)
        if action=='backtest': payload.update(start_date=(service.today()-timedelta(days=policy['lookback_days'])).isoformat(),end_date=service.today().isoformat())
    def authorize(): tasks.bound(principal,jid,token)
    def complete(receipt):
        tasks.complete(principal,jid,token,receipt)
        _close_batch(service,docs,job)
    return execute(service,docs,{'action':action,'state_version':version},run_id,payload,authorize,complete)


def _close_batch(service, docs, job):
    rows=service.store._connect().execute("SELECT e.status FROM executions e JOIN execution_jobs x ON x.execution_id=e.id JOIN research_jobs j USING(job_id) WHERE x.mandate_id=? AND x.revision=? AND json_extract(j.checkpoint_json,'$.day')=?",(job.mandate_id,job.mandate_revision,job.checkpoint.get('day'))).fetchall()
    states=[r['status'] for r in rows]
    if not states or any(s in ('queued','running') for s in states): return
    status='completed' if all(s=='succeeded' for s in states) else 'partial'
    evolution.record_closed_loop_run(docs,run_at=datetime.fromtimestamp(service.clock(),timezone.utc).isoformat(),status_value=status,action_count=states.count('succeeded'))


def tick(service, principal):
    # 旧内部入口仅兼容调用；不持有自己的队列、租约或重试规则。
    job=service.tasks.claim(principal,'strategy-adapter',lane='strategy_compute')
    return run(service,principal,job['job_id'],job['lease_token']) if job else {'status':'idle'}
