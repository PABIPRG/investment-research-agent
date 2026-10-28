export type Position = {
  quantity_unit?: '股' | '份'
  ticker: string
  name?: string
  display_name?: string | null
  name_source?: string
  quantity: number
  cost_price: number | null
  position_time?: string
}
export type Watch = {
  ticker: string
  name: string
  display_name?: string | null
  reason: string
  added_at: string
}
export type Trade = {
  name?: string
  display_name?: string | null
  name_source?: string
  quantity_unit?: '股' | '份'
  request_id: string
  ticker: string
  side: string
  quantity: number
  price: number
  fees: number
  traded_at: string
  recorded_at: string
  affects_holdings: boolean
  voided?: boolean
  revision_no?: number
}
export type Correction = {
  ticker: string
  name?: string
  recorded_at: string
  before?: Position
  after?: Position
  reason: string
}
export type Revision = {
  previous: Trade
  amended: Partial<Trade> | null
  revision_no: number
  revised_at: string
  reason: string
}
export type Facts = {
  version: number
  status: string
  holdings_status: string
  watchlist_status: string
  updated_at: string | null
  holdings: Position[]
  watchlist: Watch[]
  trades: Trade[]
  revisions: Revision[]
  corrections: Correction[]
}
export type Preview = {
  preview_id: string
  fact_version: number
  before: Facts
  after: Facts
  impact: { gaps?: { detail: string }[]; entry?: { name?: string } }
}
export type EditTarget = {
  kind: 'holding' | 'watchlist' | 'trade' | 'revision' | 'remove'
  position?: Position
  trade?: Trade
  watch?: Watch
  securityName?: string
}
export type Security = { code: string; name: string; market?: string; exchange?: string }
export const fmt = (value: number | null | undefined) =>
  value == null ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: 6 })
export const date = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString('zh-CN') : '—'
export const localTime = (value?: string) => {
  const d = value ? new Date(value) : new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
export const quantityUnit = (value?: { ticker?: string; code?: string; quantity_unit?: string }) =>
  value?.quantity_unit ||
  (/^(?:5[01268]\d{4}|159\d{3})$/.test(value?.ticker || value?.code || '') ? '份' : '股')
