"""普通绝对价格规则：沿用委托/attempt/证据/联系，不启动模型。"""
import json
import math
from ..contracts import Invalid
from .market_sources import collect_market


def eligible(revision):
    policy = revision.get('contact_policy', {})
    if revision.get('scope', {}).get('operation') != 'market_quote' or policy.get('mode', 'condition') not in {'condition', 'periodic_check'}:
        return False
    def price(c, depth=0):
        if not isinstance(c, dict) or depth > 4:
            return False
        if c.get('type') in {'all', 'any'}:
            children = c.get('conditions')
            return isinstance(children, list) and 1 <= len(children) <= 8 and all(price(x, depth+1) for x in children)
        threshold = c.get('threshold')
        return (c.get('type') == 'numeric' and c.get('metric') == 'price'
                and c.get('operator') in {'>', '>=', '<', '<=', '==', '!='}
                and type(threshold) in (int, float) and math.isfinite(threshold)
                and c.get('unit') == 'CNY/share' and c.get('method_version') == 'market_v1')
    return price(policy.get('condition'))


def binding(core, execution_id, principal):
    row = core.store._connect().execute('''SELECT r.scope_json,r.contact_policy_json FROM execution_jobs x
        JOIN mandates m USING(mandate_id) JOIN mandate_revisions r ON r.mandate_id=x.mandate_id
        AND r.revision=x.revision WHERE x.execution_id=? AND m.principal_id=?''', (execution_id, principal)).fetchone()
    if not row:
        return False
    return eligible({'scope': json.loads(row['scope_json']), 'contact_policy': json.loads(row['contact_policy_json'])})


def run(server, attempt, token, loader=None):
    repo, core = server.repo, server.mandates
    # 与finish相同的能力校验及回执幂等；重送不重新抓取报价。
    with repo.connection() as db:
        a, stored = repo._attempt(db, attempt, token)
        if stored['principal'] != server.config['principal']:
            raise PermissionError('wrong owner')
        if a['result_hash']:
            return repo.finish(attempt, token, json.loads(stored['result']))
    job = repo.active(attempt, token)
    if not binding(core, job['execution_id'], server.config['principal']):
        raise Invalid('本次执行不是已确认的纯价格条件委托')
    document = core.bound_source(job['execution_id'])
    if document is None:
        document = loader(job['scope']) if loader else collect_market(job['scope'], server.market, server.calendar)
    evidence = repo.save_evidence(attempt, token, document)
    repo.runtime_receipt(attempt, token, {'session_id': 'program:price-condition-v1', 'message_id': 'calculation:'+attempt})
    if document.get('status') != 'ok':
        return repo.finish(attempt, token, {'status': 'failed', 'error': '价格条件暂不能核对：所需报价缺失、已过期或来源无法核验；保留未知，不视为未到价。'})
    row = document['values']['items'][0]
    # 条件结果与发送资格仍由receive_results/ContactDecisionService按正式规则计算。
    return repo.finish(attempt, token, {'status': 'succeeded', 'execution_id': job['execution_id'], 'scope': job['scope'],
        'evidence_ids': [evidence['evidence_id']], 'summary': f"已按来源报价核对价格条件：{row.get('name') or row['code']}（{row['code']}）价格 {row['price']} 元/股，来源时间 {row['as_of']}。条件比较由程序执行，提醒是否送达请查看联系记录；不下单、不修改持仓。"})
