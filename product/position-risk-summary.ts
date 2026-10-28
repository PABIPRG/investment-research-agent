const labels:Record<string,string>={global:'全局持仓风险配置',override:'单仓覆盖',remove_override:'删除单仓覆盖并继承全局',rearm:'重新布防'}
const kinds:Record<string,string>={take_profit:'止盈',stop_loss:'止损'}
export function positionRiskQuestion(p:any):string{
  const a=p.payload,c=a.config
  const lines=[`确认${labels[a.operation]}？${a.ticker?'证券：'+a.ticker:''}${a.kind?' · '+kinds[a.kind]:''}`]
  if(c){
    lines.push(c.monitoring_disabled?'停用此范围的持仓风险监测。':'启用以下目标：')
    for(const kind of ['take_profit','stop_loss'])lines.push(`${kinds[kind]}：${!c[kind].enabled?'关闭':c[kind].mode==='percent'?`${c[kind].value*100}%（以激活时成本计算）`:`${c[kind].value} 元`}`)
    lines.push(`生效：${c.effective_at||'确认后'}；到期：${c.expires_at||'不设到期'}`)
  }
  for(const plan of p.impact.plans){
    lines.push(`${plan.ticker}：${({active:'生效',scheduled:'等待生效',disabled:'停用',expired:'已到期',unconfigured:'未配置',cost_unknown:'成本未知，不能激活'} as Record<string,string>)[plan.status]||plan.status}`)
    for(const [kind,target] of Object.entries(plan.targets) as [string,any][])lines.push(`  ${kinds[kind]}目标 ${target.resolved_price} 元；激活成本 ${target.basis_cost} 元`)
  }
  lines.push(p.impact.notice)
  return lines.join('\n')
}
