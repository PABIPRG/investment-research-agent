"""事件→有界 DSH 假设→待确认建议；worker 不能修改正式策略或计划。"""
import json
import math
import secrets
import uuid
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, Missing, digest
from .validation import exact, definition
from .storage import Documents
from . import schedule, suggestions
from .legacy import priors
from .legacy.runtime import runtime


def ingest(service, principal, events):
    if not isinstance(events, list) or len(events) > 100: raise Invalid('每批最多接受 100 条策略来源事件')
    accepted = []
    with service.store.transaction():
        db = service.store._connect(); policy = schedule.read(service, principal)
        docs = Documents(service.store, principal)
        allowed = {s['code'] for sid in policy['strategy_ids'] for s in (docs.get('strategies', sid) or {}).get('securities', [])}
        for event in events:
            exact(event, ('id', 'source', 'observed_at', 'title', 'summary', 'securities', 'evidence_ref'))
            for key, limit in [('id', 200), ('source', 200), ('title', 300), ('summary', 4000), ('evidence_ref', 300)]: text(event[key], key, limit)
            at = event['observed_at']
            if type(at) not in (int, float) or not math.isfinite(at) or at > service.clock() + 60 or at < service.clock() - 86400:
                raise Invalid('事件来源采集时间无效或超过 24 小时，不能生成当前候选')
            securities = event['securities']
            # 复用正式策略的证券验证，模型不得扩大来源和授权证券范围。
            normalized = definition({'name': '事件范围', 'kind': 'momentum', 'params': {}, 'securities': securities, 'direction': '其他', 'rationale': '仅用于范围校验'})
            fp = digest(event)
            old = db.execute('SELECT fingerprint FROM strategy_events WHERE principal=? AND id=?', (principal, event['id'])).fetchone()
            if old and old['fingerprint'] != fp: raise Conflict('同一来源事件不能替换内容')
            db.execute('INSERT OR IGNORE INTO strategy_events VALUES(?,?,?,?,?)', (principal, event['id'], fp, canonical(event), at))
            if not policy['enabled'] or not policy['event_candidates'] or not set(normalized['symbols']).issubset(allowed): continue
            from ..research_partner.models import EventEnvelope
            from ..research_partner.strategy_plans import now
            envelope=EventEnvelope(event_id='STR_EVENT_'+digest([principal,policy['revision'],policy['generation'],event['id']]),
                hook_type='strategy.source',producer='strategy-evidence',occurred_at=now(service),observed_at=now(service),
                payload={'mandate_id':policy['mandate_id'],'revision':policy['revision'],'source_event_id':event['id']})
            service.store.record_event(envelope)
            jid = service.tasks.enqueue(principal,policy,'candidate','event:'+event['id'],{'event_id':event['id']},envelope.event_id)
            accepted.append(jid)
    return {'queued': accepted}


def claim(service, principal, worker_id):
    return service.tasks.claim(principal, worker_id, lane='strategy_candidate')


def heartbeat(service, principal, job_id, token):
    return service.tasks.heartbeat(principal, job_id, token)


def finish(service, principal, job_id, token, result):
    with service.store.transaction():
        db = service.store._connect(); row = service.tasks.bound(principal, job_id, token, terminal=True)
        if row['result_hash']:
            previous=json.loads(row['result'])
            if previous['strategy_input_hash'] != digest(result): raise Conflict('同一执行不能重复提交不同结果')
            return previous['strategy_receipt']
        scope=json.loads(row['scope'])
        if scope['action'] != 'candidate': raise Invalid('不是候选任务')
        event_id=service.store.get_job(job_id).checkpoint['event_id']
        if not isinstance(result, dict): raise Invalid('策略候选结果无效')
        if result.get('status') == 'failed':
            exact(result, ('status', 'error')); text(result['error'], '失败原因', 1000)
            receipt = {'status': 'failed', 'error': result['error'], 'suggestions': []}
        else:
            exact(result, ('status', 'candidates'))
            if result['status'] != 'completed' or not isinstance(result['candidates'], list) or len(result['candidates']) > 3:
                raise Invalid('策略候选数量或状态无效')
            event = json.loads(db.execute('SELECT document FROM strategy_events WHERE principal=? AND id=?', (principal, event_id)).fetchone()[0])
            allowed = {s['code']: s['name'] for s in event['securities']}; docs = Documents(service.store, principal)
            saved = []
            for candidate in result['candidates']:
                value = definition(candidate)
                if value['source_evidence_ids'] or not set(value['symbols']).issubset(allowed): raise Invalid('候选超出事件证券范围或伪造来源')
                # 名称与证据由来源绑定，模型只提出规则和假设。
                candidate = {**candidate, 'securities': [{'code': s['code'], 'name': allowed[s['code']]} for s in value['securities']]}
                sid = suggestions.add(service, docs, 'event', event_id, candidate,
                    [{'event_id': event['id'], 'source': event['source'], 'evidence_ref': event['evidence_ref'], 'observed_at': event['observed_at']}])
                if sid: saved.append(sid)
            receipt = {'status': 'completed', 'suggestions': saved, 'requires_confirmation': True}
        return service.tasks.complete(principal,job_id,token,receipt,input_hash=digest(result))
