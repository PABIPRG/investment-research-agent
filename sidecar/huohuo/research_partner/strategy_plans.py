"""策略计划是核心持有的有类型委托；策略页面只是此状态的投影。"""
import json
from datetime import datetime, timezone
from ..contracts import canonical
from ..execution import Conflict
from .commands import MandateCreateRequest, MandateReviseRequest, MandateStatusRequest

KIND = 'strategy_validation'


def now(service):
    return datetime.fromtimestamp(service.clock(), timezone.utc)


def binding(service, principal):
    return service.store._connect().execute('SELECT m.* FROM mandate_workflows w JOIN mandates m USING(mandate_id) WHERE w.principal=? AND w.kind=?', (principal, KIND)).fetchone()


def read(service, principal):
    from ..strategies.schedule import DEFAULT
    row = binding(service, principal)
    if not row: return {**DEFAULT, 'next_at': None, 'updated_at': None, 'mandate_id': None, 'generation': 0}
    revision = service.store.get_revision(row['mandate_id'], row['current_revision'])
    schedules = service.store.list_schedules(row['mandate_id'], revision=row['current_revision'], active_only=True)
    generation = service.store._connect().execute('SELECT generation FROM mandate_generation WHERE mandate_id=?', (row['mandate_id'],)).fetchone()[0]
    return {**revision.scope['policy'], 'revision': row['current_revision'], 'enabled': row['status'] == 'tracking',
            'next_at': schedules[0].next_due_at.timestamp() if schedules and row['status'] == 'tracking' else None,
            'updated_at': datetime.fromisoformat(row['updated_at']).timestamp(), 'mandate_id': row['mandate_id'], 'generation': generation}


def apply(service, principal, payload, *, legacy=False):
    core = service.store.mandates
    db = service.store._connect(); current = binding(service, principal)
    if not legacy and payload['revision'] != (current['current_revision'] if current else 0):
        raise Conflict('后台计划已更新，请重新预览')
    hour, minute = map(int, payload['daily_time'].split(':'))
    policy = {k:v for k,v in payload.items() if k not in ('revision', 'enabled')}
    scope = {'kind': KIND, 'policy': policy}
    contact = {'mode':'periodic_check','channels':['app'], 'max_retries':0,
               'condition':{'type':'semantic','claim':'strategy_review','evidence_required':True},
               'schedule':{'cron':f'{minute} {hour} * * 1-5','timezone':'Asia/Shanghai','catchup_seconds':86400,'trading_days_only':False}}
    data = dict(goal='策略后台验证', scope=scope, triggers=[], contact_policy=contact,
                subjects=[{'entity_id':sid} for sid in policy['strategy_ids']],
                basis={'kind':KIND, 'confirmed_policy':payload, 'legacy_migration':legacy})
    key = f'strategy-plan:{payload["revision"]}:{int(legacy)}'
    ctx = core.context(principal)
    if current:
        mid = current['mandate_id']
        core.service.revise(ctx, mid, MandateReviseRequest(**data, expected_revision=current['current_revision'], idempotency_key=key))
        core.invalidate(mid)
    else:
        view = core.service.create(ctx, MandateCreateRequest(**data, idempotency_key=key))
        mid = view['mandate']['mandate_id']
        db.execute('INSERT INTO mandate_workflows VALUES(?,?,?)', (principal, KIND, mid))
        db.execute('INSERT INTO mandate_generation VALUES(?,0)', (mid,))
    updated = service.store.get_mandate_internal(mid)
    target = 'tracking' if payload['enabled'] else 'paused'
    if updated.status != target:
        action = core.service.resume if payload['enabled'] else core.service.pause
        action(ctx, mid, MandateStatusRequest(expected_revision=updated.current_revision, idempotency_key=key+':status'))
    return read(service, principal)


def assert_active(service, principal, revision):
    policy = read(service, principal)
    if not policy['enabled'] or policy['revision'] != revision:
        raise Conflict('后台计划已停止或改约；本次结果未生效')
    return policy
