"""升级旧候选计划；历史只读保留，未知在途工作不重放。"""
import json
from ..contracts import canonical
from .strategy_plans import apply


def migrate(service):
    db=service.store._connect()
    with service.store.transaction():
        if db.execute("SELECT 1 FROM meta WHERE key='strategy_core_upgrade_v1'").fetchone():return
        for old in db.execute('SELECT * FROM legacy_strategy_schedules').fetchall():
            from ..strategies.schedule import validate_policy
            payload=validate_policy(json.loads(old['policy']))
            confirmed=False
            previews=db.execute("SELECT payload,result FROM strategy_previews WHERE principal=? AND action='schedule' AND status='committed'",(old['principal'],)).fetchall()
            for preview in previews:
                command=json.loads(preview['payload'])['command']
                receipt=json.loads(preview['result']) if preview['result'] else {}
                if command.get('revision')==old['revision']-1 and {k:v for k,v in command.items() if k!='revision'}=={k:v for k,v in payload.items() if k!='revision'} and receipt.get('run',{}).get('status')=='completed':confirmed=True
            if payload['enabled'] and not confirmed:
                payload={**payload,'enabled':False}
            policy=apply(service,old['principal'],payload,legacy=True)
            if old['next_at'] and policy['enabled']:
                from datetime import datetime,timezone
                db.execute('UPDATE mandate_schedules SET next_due_at=? WHERE mandate_id=? AND revision=?',(datetime.fromtimestamp(old['next_at'],timezone.utc).isoformat(),policy['mandate_id'],policy['revision']))
            for table,candidate in [('legacy_strategy_background_jobs',False),('legacy_strategy_planner_jobs',True)]:
                rows=db.execute(f"SELECT * FROM {table} WHERE principal=? AND revision=? ",(old['principal'],old['revision'])).fetchall()
                for row in rows:
                    if not policy['enabled']:continue
                    action='candidate' if candidate else row['action']
                    data={'event_id':row['event_id']} if candidate else {'day':row['day'],'strategy_id':row['strategy_id']}
                    data['legacy_id']=row['id']
                    key='event:'+row['event_id'] if candidate else f"{row['day']}:{row['strategy_id']}:{action}"
                    if row['status'] not in ('pending','running'):
                        from .models import ResearchJob
                        from .strategy_plans import now
                        from ..execution import digest
                        jid='JOB_'+digest([policy['mandate_id'],policy['revision'],policy['generation'],key])[:32]
                        at=now(service)
                        # 只导入业务历史与已消费槽；不伪造 execution/attempt 或研究证据。
                        state='completed' if row['status'] in ('completed','skipped') else 'cancelled' if row['status']=='cancelled' else 'failed'
                        data['imported_terminal_status']=row['status']
                        service.store.create_job(ResearchJob(job_id=jid,mandate_id=policy['mandate_id'],mandate_revision=policy['revision'],
                            action='strategy.'+action,status=state,next_run_at=at,dedupe_key='strategy:'+jid,checkpoint=data,
                            budget={'max_attempts':0},cancel_generation=policy['generation'],created_at=at,updated_at=at))
                        continue
                    jid=service.tasks.enqueue(old['principal'],policy,action,key,data)
                    ex=db.execute('SELECT execution_id FROM execution_jobs WHERE job_id=?',(jid,)).fetchone()[0]
                    if not candidate and row['run_id']:
                        db.execute('UPDATE strategy_runs SET execution_id=? WHERE id=?',(ex,row['run_id']))
                    if row['status']=='running':
                        # 新 attempt 仅表示迁移中断；从不复用旧租约，也不提交新 DSH 请求。
                        job=service.tasks.repo.claim('migration:interrupted',lane='strategy',principal=old['principal'],execution_id=ex)
                        if job:
                            db.execute("UPDATE executions SET status='interrupted',revision=revision+1 WHERE id=?",(ex,))
                            db.execute("UPDATE attempts SET status='interrupted',lease_until=? WHERE id=?",(service.clock(),job['attempt_id']))
                            service.tasks.repo._event(db,ex,'execution.interrupted',{'reason':'legacy_in_flight_migration','legacy_id':row['id']})
        # 旧待确认预览绑定的是旧计划版本；升级后必须刷新重新确认。
        db.execute("UPDATE strategy_previews SET status='interrupted' WHERE action='schedule' AND status='pending'")
        service.tasks.route()
        for table in ('legacy_strategy_schedules','legacy_strategy_background_jobs','legacy_strategy_planner_jobs'):
            for action in ('INSERT','UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS freeze_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'legacy strategy archive is read only'); END")
        db.execute("INSERT INTO meta VALUES('strategy_core_upgrade_v1','completed')")
