"""核心策略任务交接：复用 research_jobs → executions → attempts。"""
import json
from datetime import datetime, timezone
from ..contracts import Invalid, canonical
from ..execution import Conflict, digest
from .models import ResearchJob
from .strategy_plans import KIND, binding, read, assert_active, now

ACTIONS = ('events', 'backtest', 'shadow', 'recall', 'evolve', 'candidate')


def validate_execution_scope(value):
    if not isinstance(value, dict) or set(value) != {'kind','operation','mandate_id','revision','generation','job_id','action'}:
        raise Invalid('invalid internal strategy scope')
    if value['kind'] != 'strategy' or value['operation'] != 'strategy_task' or value['action'] not in ACTIONS:
        raise Invalid('unsupported strategy execution')
    if type(value['revision']) is not int or type(value['generation']) is not int or value['revision'] < 1 or value['generation'] < 0:
        raise Invalid('invalid strategy version')
    for key, prefix in [('mandate_id','MND_'),('job_id','JOB_')]:
        import re
        if not isinstance(value[key],str) or not re.fullmatch(prefix+r'[a-f0-9]{32}',value[key]): raise Invalid('invalid core binding')
    return value


class StrategyTasks:
    def __init__(self, service):
        self.service = service
        self.core = service.store.mandates
        self.store, self.repo = service.store, self.core.repo

    def enqueue(self, principal, policy, action, key, payload, event_id=None):
        assert_active(self.service, principal, policy['revision'])
        db = self.store._connect(); jid = 'JOB_'+digest([policy['mandate_id'],policy['revision'],policy['generation'],key])[:32]
        old = db.execute('SELECT job_id FROM research_jobs WHERE job_id=?',(jid,)).fetchone()
        if old: return jid
        at = now(self.service)
        job = ResearchJob(job_id=jid,mandate_id=policy['mandate_id'],mandate_revision=policy['revision'],
            trigger_event_id=event_id, action='strategy.'+action, next_run_at=at, dedupe_key='strategy:'+jid,
            checkpoint=payload, budget={'max_attempts':1},cancel_generation=policy['generation'],created_at=at,updated_at=at)
        self.store.create_job(job)
        scope = dict(kind='strategy',operation='strategy_task',mandate_id=policy['mandate_id'],revision=policy['revision'],generation=policy['generation'],job_id=jid,action=action)
        ex = self.repo.create_strategy(principal,'core:'+jid,scope,'策略验证：'+action)
        db.execute('INSERT INTO execution_jobs VALUES(?,?,?,?,?,?)',(ex['execution_id'],jid,policy['mandate_id'],policy['revision'],policy['generation'],'none'))
        return jid

    def route_event(self, event):
        mid = event.payload.get('mandate_id')
        m = self.store.get_mandate_internal(mid) if mid else None
        rev = self.store.get_revision(mid,m.current_revision) if m else None
        if not rev or rev.scope.get('kind') != KIND: return None
        if event.hook_type == 'strategy.source':
            if m.status!='tracking' or event.payload.get('revision')!=m.current_revision:return 0
            policy=read(self.service,m.principal_id)
            if not policy['event_candidates']:return 0
            source=event.payload['source_event_id']
            self.enqueue(m.principal_id,policy,'candidate','event:'+source,{'event_id':source},event.event_id)
            return 1
        # 建立、恢复、改约不触发证券 baseline，也不提前执行尚未到期的策略验证。
        if event.hook_type != 'schedule.due': return 0
        if m.status != 'tracking' or event.payload.get('revision') != m.current_revision: return 0
        from zoneinfo import ZoneInfo
        day = event.occurred_at.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
        if day != self.service.today().isoformat(): return 0
        policy = read(self.service,m.principal_id); count = 0
        for action in ACTIONS:
            subjects = policy['strategy_ids'] if action in policy['actions'] else ['strategy_pool'] if (action=='events' and policy['event_candidates']) or (action=='recall' and policy['archive_recall']) else []
            for sid in subjects:
                self.enqueue(m.principal_id,policy,action,f'{day}:{sid}:{action}',{'day':day,'strategy_id':sid},event.event_id)
                count += 1
        return count

    def route(self):
        """核心维护待执行时效与终态投影；从不重领未知的在途任务。"""
        db = self.store._connect()
        rows = db.execute("SELECT e.id,e.status,j.job_id,j.checkpoint_json FROM executions e JOIN execution_jobs x ON x.execution_id=e.id JOIN research_jobs j ON j.job_id=x.job_id WHERE json_extract(e.scope,'$.kind')='strategy' AND (e.status='queued' OR j.status IN ('pending','running') OR EXISTS(SELECT 1 FROM strategy_runs sr WHERE sr.execution_id=e.id AND sr.status='running'))").fetchall()
        for row in rows:
            data = json.loads(row['checkpoint_json'])
            expired = row['status']=='queued' and data.get('day') and data['day'] < self.service.today().isoformat()
            if expired:
                db.execute("UPDATE executions SET status='cancelled',revision=revision+1,updated_at=? WHERE id=?",(self.repo.clock(),row['id']))
                db.execute("UPDATE research_jobs SET status='cancelled',last_error='停机期间未开始的任务已合并到最新日程' WHERE job_id=?",(row['job_id'],))
            elif row['status'] in ('interrupted','cancelled'):
                db.execute('UPDATE research_jobs SET status=?,last_error=COALESCE(last_error,?) WHERE job_id=?',('failed' if row['status']=='interrupted' else 'cancelled','执行已中断，不自动重放' if row['status']=='interrupted' else '执行已取消',row['job_id']))
                db.execute('UPDATE strategy_runs SET status=?,error=?,updated_at=? WHERE execution_id=? AND status=\'running\'',(row['status'],'执行已中断或撤销；迟到结果不生效',self.repo.clock(),row['id']))

    def claim(self, principal, worker, lane='strategy'):
        self.repo.recover()
        self.core.tick()
        from ..strategies.legacy.runtime import runtime
        with self.store.transaction(), runtime(self.service.clock):
            job = self.repo.claim(worker,lane=lane,principal=principal)
            if job:
                scope = job['scope']; data = self.store.get_job(scope['job_id']).checkpoint
                job.update(job_id=scope['job_id'],task_kind='strategy',action=scope['action'],payload=data)
                if scope['action']=='candidate':
                    from ..strategies.legacy.priors import build_hint
                    from ..strategies.storage import Documents
                    event = json.loads(self.store._connect().execute('SELECT document FROM strategy_events WHERE principal=? AND id=?',(principal,data['event_id'])).fetchone()[0])
                    if event['observed_at'] < self.repo.clock()-86400:
                        self.complete(principal,scope['job_id'],job['lease_token'],{'status':'failed','error':'来源事件已过期','suggestions':[]})
                        return None
                    job.update(event=event,priors=build_hint(Documents(self.store,principal)),deadline=self.repo.clock()+120,
                        policy='strategy-candidate-v1',allowed_rules=['ma_cross','momentum','breakout','rsi_reversal','bollinger','volume_breakout'],max_candidates=3)
                self.store._connect().execute("UPDATE research_jobs SET status='running',attempt_count=attempt_count+1 WHERE job_id=?",(scope['job_id'],))
            return job

    def bound(self, principal, jid, token, terminal=False):
        db = self.store._connect()
        row = db.execute('SELECT e.*,a.id AS attempt_id,a.started_at,a.token_hash,a.result_hash,a.result_receipt FROM execution_jobs x JOIN executions e ON e.id=x.execution_id JOIN attempts a ON a.id=e.current_attempt WHERE x.job_id=? AND e.principal=?',(jid,principal)).fetchone()
        if not row: raise Conflict('策略任务不存在或尚未领取')
        attempt, execution = self.repo._attempt(db,row['attempt_id'],token)
        if terminal and attempt['result_hash']: return row
        self.repo._active(db,row['attempt_id'],token)
        if json.loads(row['scope'])['action']=='candidate' and row['started_at']+120 <= self.repo.clock(): raise Conflict('模型任务已超过运行上限')
        return row

    def heartbeat(self, principal, jid, token):
        with self.store.transaction():
            row = self.bound(principal,jid,token)
            return self.repo.heartbeat(row['attempt_id'],token)

    def complete(self, principal, jid, token, receipt, input_hash=None):
        row = self.bound(principal,jid,token); scope = json.loads(row['scope'])
        run = receipt.get('run',{})
        failed = receipt.get('status')=='failed' or run.get('status')=='failed'
        result = {'status':'failed','error':receipt.get('error') or run.get('error') or '策略任务失败'} if failed else {
            'status':'succeeded','execution_id':row['id'],'scope':scope,'summary':receipt.get('note') or '策略研究任务已保存；正式采纳仍遵守用户确认',
            'evidence_ids':[self.repo.save_evidence(row['attempt_id'],token,{'status':'ok','scope':scope,'strategy_receipt':receipt})['evidence_id']]}
        result['strategy_receipt'] = receipt
        if input_hash: result['strategy_input_hash'] = input_hash
        self.repo.finish(row['attempt_id'],token,result,_strategy_validated=True)
        self.core.receive_results(self.store._connect())
        return receipt

    def views(self, principal, candidates=False):
        rows = self.store._connect().execute("SELECT j.*,e.id AS execution_id,e.status AS execution_status,e.result,r.id AS run_id FROM research_jobs j JOIN execution_jobs x USING(job_id) JOIN executions e ON e.id=x.execution_id LEFT JOIN strategy_runs r ON r.execution_id=e.id WHERE e.principal=? AND json_extract(e.scope,'$.kind')='strategy' AND (j.action='strategy.candidate')=? ORDER BY j.created_at DESC,j.job_id LIMIT 30",(principal,int(candidates))).fetchall()
        result = []
        for row in rows:
            payload=json.loads(row['checkpoint_json']); state={'queued':'pending','succeeded':'completed'}.get(row['execution_status'],row['execution_status'])
            receipt=(json.loads(row['result']) if row['result'] else {}).get('strategy_receipt',{})
            error=row['last_error'] or receipt.get('error') or receipt.get('run',{}).get('error')
            if receipt.get('run',{}).get('status')=='skipped':state='skipped'
            result.append(dict(id=row['job_id'],**payload,action=row['action'].split('.')[1],status=state,run_id=row['run_id'],execution_id=row['execution_id'],mandate_id=row['mandate_id'],updated_at=datetime.fromisoformat(row['updated_at']).timestamp(),error=error))
        # 未迁成活动任务的旧记录只作为历史展示，不伪造 attempt 或重新执行。
        table='legacy_strategy_planner_jobs' if candidates else 'legacy_strategy_background_jobs'
        archived=self.store._connect().execute(f"SELECT * FROM {table} WHERE principal=? AND id NOT IN (SELECT json_extract(checkpoint_json,'$.legacy_id') FROM research_jobs JOIN execution_jobs USING(job_id) WHERE json_extract(checkpoint_json,'$.legacy_id') IS NOT NULL) ORDER BY created_at DESC LIMIT 30",(principal,)).fetchall()
        for row in archived:
            item=dict(row)
            for key in ('token_hash','worker_id','lease_until','started_at','result'):item.pop(key,None)
            item['archived']=True
            if item['status'] in ('pending','running'):
                item.update(status='cancelled' if item['status']=='pending' else 'interrupted',error='旧任务已归档，未扩大旧授权或自动重放')
            result.append(item)
        return sorted(result,key=lambda item:item['updated_at'],reverse=True)[:30]
