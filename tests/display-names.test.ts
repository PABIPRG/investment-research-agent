import test from 'node:test'
import assert from 'node:assert/strict'
import { hydrateDisplayNames } from '../product/ui/investment/display-names.js'
import { recordedName, securityName } from '../product/ui/business-model.js'
import type { Facts } from '../product/ui/investment/types.js'

test('缺名查询分批进行，失败的前八项不会饿死后面的代码，已知名称和基金不误查', async () => {
  const codes = Array.from({ length: 10 }, (_, i) => String(600000 + i))
  const facts = {
    holdings: [
      ...codes.map((ticker) => ({ ticker, quantity: 1, cost_price: null })),
      { ticker: '513130', quantity: 1, cost_price: null },
      { ticker: '600099', name: '已知名称', quantity: 1, cost_price: 1 },
    ],
    watchlist: [],
    trades: [],
  } as unknown as Facts
  const calls: string[] = []
  let pending = 0,
    peak = 0,
    batches = 0
  await hydrateDisplayNames(
    facts,
    async (code) => {
      pending++
      peak = Math.max(peak, pending)
      calls.push(code)
      await Promise.resolve()
      pending--
      if (code <= '600007') throw Error('合成不可用')
      return { status: 'ok' }
    },
    async () => {
      batches++
    },
  )
  assert.deepEqual(calls, codes)
  assert.ok(peak <= 4)
  assert.equal(batches, 1)
})
test('纯代码和导入占位名不遮盖目录名称，成交自身名称也能单独显示', () => {
  assert.equal(securityName('000001', '证券名称待补全', '000001'), '名称待补充')
  assert.equal(
    recordedName(
      { holdings: [], watchlist: [], trades: [{ ticker: '000001', name: '成交银行' }] },
      '000001',
    ),
    '成交银行',
  )
  assert.equal(
    recordedName({ holdings: [{ ticker: '000001', display_name: '目录银行' }] }, '000001'),
    '目录银行',
  )
})
