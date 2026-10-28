"""模型事件候选和存档召回只生成建议；正式候选必须再次预览确认。"""
import json
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, Missing, digest
from .validation import definition, exact
from .legacy import gene_archive, regime


def add(service, docs, kind, source_id, candidate, evidence):
    value = definition(candidate)
    if kind == 'archive':
        archived=next((a for a in gene_archive.all_archived(docs) if a.get('sid')==source_id),{})
        value['id'] = 'STR_' + digest([source_id,value['id'],archived.get('archived_at'),evidence[0].get('regime')])[:24]
        value['gene']=(docs.get('strategies',source_id) or {}).get('gene',value['gene'])
        value['mutated_from'] = source_id
    if docs.get('strategies', value['id']): return None
    fingerprint = digest(value); sid = 'SSG_' + digest([docs.principal, kind, source_id, fingerprint])[:32]
    document = {'candidate': value, 'evidence': evidence}
    service.store._connect().execute('INSERT OR IGNORE INTO strategy_suggestions VALUES(?,?,?,?,?,?,?,?,?)',
        (sid, docs.principal, kind, source_id, fingerprint, canonical(document), 'pending', service.clock(), None))
    return sid


def list_pending(service, principal):
    return [{**dict(row), 'document': json.loads(row['document'])} for row in service.store._connect().execute(
        "SELECT id,source_kind,source_id,document,status,created_at,strategy_id FROM strategy_suggestions WHERE principal=? ORDER BY created_at DESC,id LIMIT 50", (principal,))]


def prepare(service, docs, payload):
    exact(payload, ('suggestion_id',))
    text(payload['suggestion_id'], '候选建议', 100)
    row = service.store._connect().execute('SELECT * FROM strategy_suggestions WHERE id=? AND principal=?', (payload['suggestion_id'], docs.principal)).fetchone()
    if not row: raise Missing('候选建议不存在')
    if row['status'] != 'pending': raise Conflict('候选建议已经处理，请刷新')
    value = json.loads(row['document'])['candidate']
    if docs.get('strategies', value['id']): raise Conflict('同一策略已保存')
    if len(docs.all('strategies')) >= 100: raise Invalid('当前实例最多保存 100 项策略')
    return row, value


def accept(service, docs, payload, stamp):
    row, value = prepare(service, docs, payload)
    record = {**value, 'revision': 1, 'status': 'candidate', 'verification_status': 'insufficient',
              'backtest': {}, 'source': 'confirmed_' + row['source_kind'], 'created_at': stamp,
              'updated_at': stamp, 'evolve': {'state': 'active', 'tier': 1},
              'source_refs': json.loads(row['document'])['evidence']}
    from .legacy import ledger
    ledger.record_candidate(docs,event={'event_type':row['source_kind'],'date':stamp[:10]},direction=record['direction'],symbol_codes=record['symbols'],date=stamp[:10])
    docs.set('strategies', record['id'], record)
    service.store._connect().execute("UPDATE strategy_suggestions SET status='accepted',strategy_id=? WHERE id=?", (record['id'], row['id']))
    return record


def recall(service, docs, policy):
    market = regime.latest_regime(docs, as_of_date=service.today().isoformat()) or {}
    # 过期市场状态不成为召回依据；没有本期有效基准时明确等待。
    if market.get('date') != service.today().isoformat():
        return {'suggestions': [], 'note': '缺少本期市场环境证据，未召回归档'}
    active = [sid for sid, s in docs.all('strategies').items() if s.get('status') in ('candidate', 'active', 'watch')]
    candidates = gene_archive.revival_candidates(docs, market.get('regime'), limit=100, exclude=active)
    created = []
    for archive in candidates:
        old_id = archive.get('sid'); previous = docs.get('strategies', old_id) or {}
        if old_id not in policy['strategy_ids'] or not previous.get('securities'): continue
        value = {'name': '召回·' + str(archive.get('name', '策略'))[:90], 'kind': archive['kind'],
                 'params': archive['params'], 'securities': previous['securities'],
                 'direction': archive.get('direction', '其他'), 'rationale': '归档规则适配当前市场环境，确认后重新回测，不沿用旧收益结论'}
        suggestion = add(service, docs, 'archive', old_id, value,
                         [{'archive_id': old_id, 'regime': market.get('regime'), 'date': market['date']}])
        if suggestion: created.append(suggestion)
    return {'suggestions': created, 'note': '归档召回只生成建议，等待用户确认保存和重新验证'}
