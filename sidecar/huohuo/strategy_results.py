"""策略结果走核心 outbox 和任务历史；不自动生成通知或改变研究基准。"""
from datetime import datetime, timezone
from .contracts import canonical
from .execution import digest


def receive(core, row, result, stale):
    db = core.store._connect(); at = datetime.fromtimestamp(core.repo.clock(),timezone.utc).isoformat()
    rid = 'RES_'+row['attempt_id'].replace('-','')
    db.execute('INSERT OR IGNORE INTO research_job_results VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        (rid,row['job_id'],row['attempt_id'],'completed' if result['status']=='succeeded' else 'failed',canonical(result),digest(result.get('evidence_ids',[])),'[]',result.get('summary',''),'{}',int(stale),at))
    if not stale:
        db.execute('UPDATE research_jobs SET status=?,updated_at=?,last_error=? WHERE job_id=?',('completed' if result['status']=='succeeded' else 'failed',at,result.get('error'),row['job_id']))
    db.execute('UPDATE result_outbox SET received=1,receipt=? WHERE attempt_id=?',(canonical({'result_id':rid,'stale':stale}),row['attempt_id']))
