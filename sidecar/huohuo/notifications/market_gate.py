"""市场资料只在仍符合当前口径时获得新的发送许可；检查仅读本地。"""
import json
import sqlite3

from ..research_partner.market_sources import MARKET_OPERATIONS, validate_market_document
from ..research_partner.market_freshness import evidence_is_current
from ..market.source_transitions import source_event_is_current


def current_for_delivery(core, decision_id):
    """在 reserve 的现有事务中、写入 in_flight 之前调用。

    不创建研究或网络查询，不修改已在途许可。普通领域的投递继续服从原有
    门禁；直接到期提醒无需行情证据；市场资料缺失或无法绑定时保守拒绝。
    """
    try:
        db = core.store._connect()
        row = db.execute('''SELECT d.job_id,d.mandate_id,d.mandate_revision,d.decision,d.reason_code,
                                   j.action,j.trigger_event_id,r.scope_json
                            FROM contact_decisions d
                            JOIN research_jobs j ON j.job_id=d.job_id AND j.mandate_id=d.mandate_id
                                 AND j.mandate_revision=d.mandate_revision
                            JOIN mandate_revisions r ON r.mandate_id=d.mandate_id AND r.revision=d.mandate_revision
                            WHERE d.decision_id=?''', (decision_id,)).fetchone()
        if not row or not (row['decision'] == 'send' or (row['decision'] == 'defer' and row['reason_code'] == 'quiet_hours')):
            return False
        scope = json.loads(row['scope_json'])
        if not isinstance(scope, dict):
            return False
        if scope.get('operation') not in MARKET_OPERATIONS:
            return scope.get('operation') in {'quote_snapshot', 'company_profile', 'financial_summary'}
        if row['action'] == 'due_reminder':
            return True
        if not source_event_is_current(db, row['trigger_event_id']):
            return False
        results = db.execute('SELECT * FROM research_job_results WHERE job_id=?', (row['job_id'],)).fetchall()
        # 当前执行台账一项 job 只有一次确定结果；歧义不能择取有利结果授权。
        if len(results) != 1 or results[0]['stale'] or results[0]['outcome'] != 'completed':
            return False
        result = json.loads(results[0]['structured_result_json'])
        if not isinstance(result, dict) or result.get('status') != 'succeeded' or result.get('scope') != scope:
            return False
        refs = result.get('evidence_ids')
        if not isinstance(refs, list) or not 1 <= len(refs) <= 20 or not all(isinstance(ref, str) and ref for ref in refs):
            return False
        attempt = results[0]['run_id']
        binding = db.execute('''SELECT a.execution_id FROM attempts a
                               JOIN execution_jobs x ON x.execution_id=a.execution_id
                               WHERE a.id=? AND a.status='succeeded' AND x.job_id=?
                                 AND x.mandate_id=? AND x.revision=?''',
                             (attempt, row['job_id'], row['mandate_id'], row['mandate_revision'])).fetchone()
        if not binding or result.get('execution_id') != binding['execution_id']:
            return False
        for ref in refs:
            evidence = db.execute('SELECT document FROM evidence WHERE id=? AND attempt_id=?', (ref, attempt)).fetchone()
            if not evidence:
                return False
            validate_market_document(json.loads(evidence[0]), scope)
        return evidence_is_current(db, attempt, result, scope, core.repo.clock(), getattr(core.service, 'calendar', None))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, sqlite3.Error):
        return False
