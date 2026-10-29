import { money } from '../business-model.js'
export type AccountMetric = {
  value: number | null
  status: 'ok' | 'stale' | 'unavailable'
  reason: string
  currency: 'CNY'
}
export type AccountView = {
  fact_version: number
  observed_at: string
  holdings_status: string
  holdings_count: number
  watchlist_count: number
  market_value: AccountMetric
  holding_cost: AccountMetric
  daily_pnl: AccountMetric
  sources: { code: string; source: string; as_of: string; stale: boolean }[]
  missing_codes: string[]
  warnings: string[]
  scope_note: string
}
export function accountAmount(metric: AccountMetric | undefined, hidden: boolean, error: string) {
  if (error) return '读取失败'
  if (!metric) return '读取中'
  if (metric.value == null || !Number.isFinite(metric.value)) return '待补全'
  return hidden ? '••••' : money(metric.value)
}
export function accountNote(account?: AccountView, error = '') {
  if (error) return error
  if (!account) return '正在读取本地投资记录…'
  const notes: string[] = []
  if (account.holdings_status === 'not_recorded') notes.push('本地尚未录入持仓')
  if (account.market_value.status === 'stale') notes.push('市值为旧行情参考')
  if (account.market_value.value == null) notes.push(account.market_value.reason)
  if (account.holding_cost.value == null) notes.push('成本待补全')
  if (account.daily_pnl.value == null) notes.push(account.daily_pnl.reason)
  else if (account.daily_pnl.status === 'stale') notes.push('日盈亏为旧行情参考')
  if (!notes.length)
    notes.push(account.holdings_count ? '按本地持仓与来源报价计算' : '本地持仓为空')
  return notes.join(' · ')
}
