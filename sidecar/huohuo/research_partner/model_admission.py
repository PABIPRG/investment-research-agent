"""后台模型的统一准入：可信事件、当前能力与一次性提交预占由核心核验。"""
import json
from ..contracts import Invalid
from ..execution import Conflict, digest
from ..market.source_transitions import source_event_is_current
from .baseline_policy import requires_comparison_baseline
from .market_sources import MARKET_OPERATIONS, collect_market
from .market_freshness import fresh_for_contact
from .sources import trigger

POLICY = 'hook-model-gate-v1'
_DETAILS = {
    'missing_trusted_trigger': '缺少可信的明确研究请求或委托触发事件',
    'missing_active_hook': '任务没有绑定有效的 Hook 事件',
    'hook_dependency_not_matched': '事件没有命中当前委托的对象或依赖',
    'hook_source_unavailable': '触发资料缺失或无法核验',
    'hook_source_stale_or_unknown': '触发资料过期或口径未知，等待有效资料',
    'source_superseded': '触发资料已被新版本替代，本次旧任务不再研究',
    'initial_research_not_required': '本委托不需要此时启动初次研究，等待约定触发',
    'schedule_not_due_or_mismatched': '任务没有匹配当前有效的到期实例',
    'explicit_research_trigger_required': '请明确可执行的研究触发约定；不能把混合联系条件自动转成模型研究授权',
    'model_submission_already_reserved': '本次研究已经取得过提交资格，结果未知时不可自动重放',
}


def rule_kind(condition, depth=0):
    if not isinstance(condition, dict) or depth > 4:
        return 'unsupported'
    kind = condition.get('type')
    if kind in {'numeric', 'semantic'}:
        return kind
    if kind in {'all', 'any'}:
        children = condition.get('conditions', [])
        if not isinstance(children, list) or not 1 <= len(children) <= 8:
            return 'unsupported'
        kinds = {rule_kind(child, depth + 1) for child in children}
        return next(iter(kinds)) if len(kinds) == 1 else 'mixed'
    return 'unsupported'


def _decision(mode, reason, **binding):
    return dict(mode=mode, reason=reason, detail=_DETAILS.get(reason, '程序已核对任务触发依据与当前执行资格'), policy=POLICY, **binding)


def _schedule_matches(core, event, job, mode):
    p = event.payload
    schedule = core.store.get_schedule(p.get('schedule_id', ''))
    return bool(schedule and schedule.enabled and schedule.mandate_id == job.mandate_id
                and schedule.revision == job.mandate_revision and schedule.mode == mode
                and p.get('mandate_id') == job.mandate_id and p.get('revision') == job.mandate_revision
                and p.get('mode') == mode and p.get('instance_key')
                and event.producer == 'research-partner-scheduler'
                and 0 <= core.repo.clock() - event.occurred_at.timestamp() <= schedule.catchup_seconds)


def _origin(server, db, row):
    core = server.mandates
    binding = db.execute('SELECT * FROM execution_jobs WHERE execution_id=?', (row['id'],)).fetchone()
    if not binding:
        explicit = db.execute("SELECT seq FROM events WHERE execution_id=? AND kind='research.requested'", (row['id'],)).fetchone()
        return _decision('model', 'explicit_user_request', request_event_seq=explicit[0]) if explicit else _decision('blocked', 'missing_trusted_trigger')
    job = core.store.get_job(binding['job_id'])
    event = core.store.get_event(job.trigger_event_id) if job and job.trigger_event_id else None
    base = dict(job_id=binding['job_id'], mandate_id=binding['mandate_id'], revision=binding['revision'],
                generation=binding['generation'], trigger_event_id=job.trigger_event_id if job else None)
    deny = lambda reason: _decision('blocked', reason, **base)
    if not job or job.status not in {'pending', 'running'} or not event:
        return deny('missing_active_hook')
    m = core.store.get_mandate_internal(job.mandate_id)
    if not m or m.principal_id != row['principal']:
        return deny('hook_owner_mismatch')
    generation = db.execute('SELECT generation FROM mandate_generation WHERE mandate_id=?', (job.mandate_id,)).fetchone()
    if (m.status != 'tracking' or m.current_revision != job.mandate_revision
            or binding['revision'] != job.mandate_revision or not generation
            or binding['generation'] != generation[0]):
        return deny('hook_revision_or_generation_invalid')
    rev = core.store.get_revision(job.mandate_id, job.mandate_revision)
    if rev is None:
        return deny('hook_revision_missing')
    scope = json.loads(row['scope'])
    if not source_event_is_current(db, event.event_id):
        return deny('source_superseded')
    if scope.get('kind') == 'strategy':
        return _strategy_origin(server, row, job, event, base)
    if scope != rev.scope:
        return deny('hook_scope_mismatch')
    policy = rev.contact_policy
    mode = policy.get('mode', 'condition')
    kind = rule_kind(policy.get('condition'))
    base.update(source_version=event.source_version, rule_hash=digest({'triggers': rev.triggers, 'contact_policy': policy}))
    if event.hook_type in {'mandate.created', 'mandate.requirements_completed', 'mandate.resumed'}:
        if (job.action != 'baseline_review' or event.producer != 'research-partner'
                or event.payload.get('mandate_id') != job.mandate_id
                or event.payload.get('revision') != job.mandate_revision
                or mode in {'scheduled_delivery', 'due_reminder'}
                or (mode == 'periodic_check' and not requires_comparison_baseline(policy))):
            return deny('initial_research_not_required')
    elif event.hook_type == 'schedule.due':
        if not _schedule_matches(core, event, job, mode) or job.action != mode:
            return deny('schedule_not_due_or_mismatched')
    else:
        dependencies = core.store.find_active_dependencies(hook_type=event.hook_type,
            subject_ids=event.subject_ids, event_type=event.payload.get('event_type'))
        matches = [d for d in dependencies if d.mandate_id == job.mandate_id
                   and d.revision == job.mandate_revision
                   and (not event.payload.get('scope_key') or d.scope_key == event.payload['scope_key'])
                   and (not d.feature_key or d.feature_key == event.payload.get('feature_key'))]
        if job.action != 'event_review' or mode != 'condition' or not matches:
            return deny('hook_dependency_not_matched')
        if event.hook_type == 'investment.facts_revised':
            if event.payload.get('principal_id') != row['principal']:
                return deny('hook_owner_mismatch')
            collection = rev.basis.get('investment_collection')
            if collection and ((event.payload.get('change_type') == 'watchlist') != (collection.get('collection') == 'watchlist')):
                return deny('fact_dependency_not_matched')
        else:
            expected = trigger(scope, policy)
            if (not expected or event.hook_type != expected[0]['hook_type']
                    or event.payload.get('principal') != row['principal']
                    or event.payload.get('scope_key') != expected[0]['scope_key']):
                return deny('unsupported_or_unbound_hook')
            document = core.bound_source(row['id'])
            if not document or document.get('status') != 'ok' or document.get('scope') != scope:
                return deny('hook_source_unavailable')
            if scope['operation'] in MARKET_OPERATIONS | {'quote_snapshot'} and not fresh_for_contact(
                    document, scope, core.repo.clock(), getattr(server, 'calendar', None)):
                return deny('hook_source_stale_or_unknown')
    if mode == 'due_reminder':
        return deny('direct_reminder_does_not_need_model')
    if core.position_risk.bindings.for_mandate(job.mandate_id):
        reason = core.position_risk.reason(job.mandate_id)
        return deny(reason) if reason else _decision('program', 'position_rule', **base)
    if mode == 'scheduled_delivery':
        return _decision('model', 'scheduled_delivery_due', **base)
    if kind == 'numeric' and scope['operation'] in {'market_quote', 'market_technical', 'quote_snapshot'}:
        return _decision('program', 'deterministic_condition', **base)
    if kind != 'semantic':
        return deny('explicit_research_trigger_required')
    return _decision('model', 'semantic_review_hook_matched', **base)


def _strategy_origin(server, row, job, event, base):
    from .strategy_plans import read, assert_active
    service = server.strategies
    policy = read(service, row['principal'])
    assert_active(service, row['principal'], base['revision'])
    if event.payload.get('mandate_id') != job.mandate_id or event.payload.get('revision') != job.mandate_revision:
        return _decision('blocked', 'strategy_hook_mismatch', **base)
    action = json.loads(row['scope'])['action']
    if action != 'candidate':
        return _decision('program', 'strategy_calculation', **base)
    source = job.checkpoint.get('event_id')
    if (event.hook_type != 'strategy.source' or event.producer != 'strategy-evidence'
            or event.payload.get('source_event_id') != source or not policy['event_candidates']):
        return _decision('blocked', 'strategy_hook_mismatch', **base)
    record = service.store._connect().execute('SELECT document,fingerprint FROM strategy_events WHERE principal=? AND id=?', (row['principal'], source)).fetchone()
    if not record:
        return _decision('blocked', 'strategy_source_unavailable', **base)
    document = json.loads(record[0])
    base.update(source_version=record[1], rule_hash=digest(policy))
    from ..strategies.storage import Documents
    docs = Documents(service.store, row['principal'])
    allowed = {s['code'] for sid in policy['strategy_ids'] for s in (docs.get('strategies', sid) or {}).get('securities', [])}
    if (not 0 <= service.clock() - document['observed_at'] <= 86400
            or not {s['code'] for s in document['securities']}.issubset(allowed)):
        return _decision('blocked', 'strategy_source_stale_or_out_of_scope', **base)
    return _decision('model', 'strategy_source_matched', **base)


def admit(server, attempt, token, phase):
    if phase not in {'prepare', 'submit'}:
        raise Invalid('未知模型准入阶段')
    repo = server.repo
    with repo.connection(True) as db:
        a, row = repo._active(db, attempt, token)
        if row['principal'] != server.config['principal']:
            raise PermissionError('wrong owner')
        decision = _origin(server, db, row)
        decision.update(execution_id=row['id'], attempt_id=attempt, phase=phase, lease_until=a['lease_until'])
        if decision['mode'] == 'model':
            # 同一业务执行不因新 attempt、超时或丢失准入响应再次取得提交资格。
            last = db.execute("SELECT seq FROM events WHERE execution_id=? AND kind='model.submission_reserved' ORDER BY seq DESC LIMIT 1", (row['id'],)).fetchone()
            retry = db.execute("SELECT seq FROM events WHERE execution_id=? AND kind='execution.retry' ORDER BY seq DESC LIMIT 1", (row['id'],)).fetchone()
            if last and (decision.get('job_id') or not retry or retry[0] < last[0]):
                decision.update(mode='blocked', reason='model_submission_already_reserved',
                                detail=_DETAILS['model_submission_already_reserved'])
            elif phase == 'submit':
                repo._event(db, row['id'], 'model.submission_reserved', decision)
        repo._event(db, row['id'], 'model.admission', decision)
        return decision


def run_program(server, attempt, token, loader=None):
    repo, core = server.repo, server.mandates
    with repo.connection() as db:
        a, row = repo._attempt(db, attempt, token)
        if row['principal'] != server.config['principal']:
            raise PermissionError('wrong owner')
        if a['result_hash']:
            return repo.finish(attempt, token, json.loads(row['result']))
    decision = admit(server, attempt, token, 'prepare')
    if decision['mode'] != 'program':
        raise Invalid('任务未获程序执行资格')
    if decision['reason'] == 'position_rule':
        from ..position_risk.execution import run
        return run(server, attempt, token, loader)
    job = repo.active(attempt, token)
    from .price_execution import binding, run as run_price
    if binding(core, job['execution_id'], server.config['principal']):
        return run_price(server, attempt, token, loader)
    scope = job['scope']
    if scope.get('kind') == 'strategy':
        raise Invalid('策略计算使用原领域执行器')
    document = core.bound_source(job['execution_id'])
    try:
        if document is None:
            if loader:
                document = loader(scope)
            elif scope['operation'] in MARKET_OPERATIONS:
                document = collect_market(scope, server.market, server.calendar)
            else:
                document = server.researcher(scope)
        if (document.get('status') != 'ok' or document.get('scope') != scope
                or not fresh_for_contact(document, scope, repo.clock(), server.calendar)):
            return repo.finish(attempt, token, {'status': 'failed', 'error': '程序检查资料缺失、过期或口径未知；未调用模型，也不视为条件不满足。'})
        evidence = repo.save_evidence(attempt, token, document)
    except (Conflict, PermissionError):
        raise
    except Exception:
        return repo.finish(attempt, token, {'status': 'failed', 'error': '程序检查来源失败；未回退到模型研究。'})
    # 采集后重新核验暂停、版本、来源替代和能力，迟到资料不能放行。
    if admit(server, attempt, token, 'prepare')['mode'] != 'program':
        return repo.finish(attempt, token, {'status': 'failed', 'error': '程序执行资格已变化。'})
    repo.runtime_receipt(attempt, token, {'session_id': 'program:numeric-condition-v1', 'message_id': 'calculation:' + attempt})
    return repo.finish(attempt, token, {'status': 'succeeded', 'execution_id': job['execution_id'], 'scope': scope,
        'evidence_ids': [evidence['evidence_id']], 'summary': '程序已按合格来源完成数值条件检查；条件与联系资格由委托核心核验，未调用模型。'})
