import assert from 'node:assert/strict'
import { test } from 'node:test'
import { accountAmount, accountNote, type AccountView, type AccountMetric } from '../product/ui/investment/account-model.js'
const m = (value: number | null, status: AccountMetric['status'] = 'ok', reason = ''): AccountMetric => ({ value, status, reason, currency: 'CNY' })
const empty: AccountView = { fact_version: 0, observed_at: '', missing_codes: [], warnings: [], scope_note: '', holdings_status: 'not_recorded', holdings_count: 0, watchlist_count: 0, market_value: m(0), holding_cost: m(0), daily_pnl: m(0), sources: [] }
test('本地空记录显示零；加载、失败和数据缺口各自表达', () => {
  assert.equal(accountAmount(empty.market_value, false, ''), '0.00')
  assert.equal(accountAmount(empty.market_value, true, ''), '••••')
  assert.equal(accountAmount(undefined, false, ''), '读取中')
  assert.equal(accountAmount(empty.market_value, false, 'offline'), '读取失败')
  assert.equal(accountAmount({ ...empty.market_value, value: null }, false, ''), '待补全')
  assert.match(accountNote(empty), /本地尚未录入/)
  assert.equal(accountNote(empty, '读取失败，请重试'), '读取失败，请重试')
})
test('缺行情、未知成本和旧参考不会被统一写成行情未接入', () => {
  const partial = { ...empty, holdings_status: 'recorded', holdings_count: 1, market_value: m(null, 'unavailable', '行情读取失败'), daily_pnl: m(null, 'unavailable', '昨收基准待核对') } as AccountView
  assert.match(accountNote(partial), /行情读取失败/)
  assert.match(accountNote(partial), /昨收基准待核对/)
  assert.match(accountNote({ ...partial, market_value: m(12, 'stale') } as AccountView), /旧行情参考/)
  assert.doesNotMatch(accountNote(empty), /行情未接入|日收益基准缺失/)
})
