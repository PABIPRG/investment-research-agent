import type { MandateView } from './model.js'
export const triggerLabels: Record<string, string> = {
  all: '全部跟进方式',
  scheduled_delivery: '定时交付',
  periodic_check: '定时检查',
  due_reminder: '到时提醒',
  source: '资料变化',
  investment: '持仓或自选变化',
  other: '其他变化',
  unconnected: '待接入跟进',
}
const hookLabels: Record<string, string> = {
  'financial.summary_changed': '财务摘要变化',
  'company.profile_changed': '公司资料变化',
  'quote.snapshot_changed': '证券报价变化',
  'market.quote_changed': '行情变化',
  'market.technical_changed': '技术指标变化',
  'market.news_changed': '新闻变化',
  'market.brief_changed': '简报资料变化',
  'investment.facts_revised': '持仓或自选记录变化',
  'schedule.due': '约定时间到达',
}
const hookDescriptions: Record<string, string> = {
  'financial.summary_changed': '取得新的财务摘要后，核对与你的研究问题有关的变化。',
  'company.profile_changed': '公司资料更新后，核对是否影响原有判断。',
  'quote.snapshot_changed': '取得新报价后，按你保存的条件进行核对。',
  'market.quote_changed': '行情更新后，检查是否达到约定条件。',
  'market.technical_changed': '技术指标更新后，检查与你的委托有关的变化。',
  'market.news_changed': '取得新的相关消息后，再核对是否需要跟进。',
  'market.brief_changed': '盘前或盘后资料更新后，按约整理新的内容。',
  'investment.facts_revised': '你修改持仓或自选记录后，重新核对相关研究。',
  'schedule.due': '到约定时间后，按你的安排整理资料、检查条件或提醒。',
}
export function mandateHooks(item: MandateView) {
  const ids = [
    ...new Set([
      ...(item.dependencies || []).filter((d) => d.active !== false).map((d) => d.hook_type),
      ...(item.revision.triggers || []).map((t) => t.hook_type),
    ]),
  ]
  if (item.schedules?.some((s) => s.enabled !== false) && !ids.includes('schedule.due'))
    ids.push('schedule.due')
  return ids.map((id) => ({
    id,
    label: hookLabels[id] || '其他变化',
    description: hookDescriptions[id] || '另有已保存的跟进条件，具体安排请查看委托详情。',
  }))
}
export function triggerKind(item: MandateView): string {
  const mode = item.revision.contact_policy?.mode
  if (mode && mode !== 'condition') return Object.hasOwn(triggerLabels, mode) ? mode : 'other'
  const hooks = mandateHooks(item)
  if (hooks.some((h) => /^(market\.|quote\.|financial\.|company\.)/.test(h.id))) return 'source'
  if (hooks.some((h) => h.id === 'investment.facts_revised')) return 'investment'
  return hooks.length ? 'other' : 'unconnected'
}
export function matchesTrigger(item: MandateView, value: string) {
  if (value === 'all') return true
  if (value === 'investment')
    return mandateHooks(item).some((h) => h.id === 'investment.facts_revised')
  return triggerKind(item) === value
}
export function nextTrigger(item: MandateView) {
  if (item.mandate.status === 'paused') return '恢复委托后再跟进'
  if (item.mandate.status === 'ended') return '已结束'
  const mode = item.revision.contact_policy?.mode
  if (mode && mode !== 'condition') {
    const next = item.schedules
      ?.filter((s) => s.enabled !== false && Number.isFinite(Date.parse(s.next_due_at)))
      .sort((a, b) => Date.parse(a.next_due_at) - Date.parse(b.next_due_at))[0]
    if (!next) return '已约定时间，日程待核对'
    const time = new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
      timeZone: next.timezone,
    }).format(new Date(next.next_due_at))
    return `${time} · ${triggerLabels[mode] || '按约执行'}`
  }
  if (item.monitoring?.enabled) return item.monitoring.detail.split('；')[0]
  return item.monitoring?.detail || '持续资料发现尚未接入'
}
