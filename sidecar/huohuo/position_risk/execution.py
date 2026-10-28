"""在现有 execution/attempt/lease 中完成价格条件；不启动模型。"""
from ..contracts import Invalid
from ..execution import Conflict
from ..research_partner.market_sources import collect_market,MARKET_OPERATIONS

def run(server,attempt,token,loader=None):
    repo,core=server.repo,server.mandates
    job=repo.active(attempt,token)
    with core.store.transaction():
        row=core.store._connect().execute('SELECT mandate_id FROM execution_jobs WHERE execution_id=?',(job['execution_id'],)).fetchone()
        binding=core.position_risk.bindings.for_mandate(row[0]) if row else None
        if not binding or binding['principal']!=server.config['principal']:raise Invalid('本次执行不是当前用户的持仓风险目标')
        reason=core.position_risk.reason(row[0])
        if reason:raise Conflict(reason)
    document=core.bound_source(job['execution_id'])
    if document is None:
        if loader:document=loader(job['scope'])
        elif job['scope']['operation'] in MARKET_OPERATIONS:
            document=collect_market(job['scope'],server.market,server.calendar)
        else:
            from ..research_entities.bounded import collect
            document=collect(job['scope'])
    if document.get('status')!='ok':
        return repo.finish(attempt,token,{'status':'failed','error':'持仓风险行情不可用；未把失败当作未命中或可发送'})
    evidence=repo.save_evidence(attempt,token,document)
    repo.runtime_receipt(attempt,token,{'session_id':'program:position-risk-v1','message_id':'calculation:'+attempt})
    # 数值和单位由 receive_results/bound_metrics 与正式条件程序重新核验。
    return repo.finish(attempt,token,{'status':'succeeded','execution_id':job['execution_id'],'scope':job['scope'],
        'evidence_ids':[evidence['evidence_id']], 'summary':f"持仓价格条件程序复核；激活成本 {binding['basis_cost']} 元，目标价 {binding['resolved_price']} 元。只按合格报价比较，不产生交易。"})
