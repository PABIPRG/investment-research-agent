// Pure shared confirmation text for native chat and product UI.
export function personalizationQuestion(p:any):string{
  const a=p.payload
  if(a.action==='learning')return a.enabled?'启用本机学习？将在你查看卡片时记录本机阅读与反馈，用于兴趣排序和偏好复盘。可暂停或清除，最长保留90天。不修改风险偏好、委托或交易。':'暂停本机学习？停止记录新的阅读与反馈，已有记录保留，可另行清除。'
  if(a.action==='clear')return `清除本机学习记录？将清除 ${p.before.learning.record_count} 条阅读/反馈及关联预览、回执、行为审计，旧预览随之失效；清除后无法恢复。${p.before.learning.enabled?'当前学习已启用，清除后新的操作仍会记录；可先暂停再清除。':'当前学习已暂停，清除后继续暂停。'}风险问卷、投资记录、策略和委托保留。`
  const card=p.before.cards.cards.find((c:any)=>c.card_id===a.card_id)
  return `确认反馈“${p.impact?.subject?.title||card?.title||a.card_id}”：${({useful:'值得关注',useless:'减少此类',neutral:'撤销反馈'} as Record<string,string>)[a.sentiment]}？仅影响本机兴趣排序，不改风险偏好、委托或交易。`
}
