import test from 'node:test'
import assert from 'node:assert/strict'
import { ReadCycle } from '../product/ui/shared/read-cycle.js'
test('新读取和写入都撤销旧读取资格，迟到回调不能覆盖新快照', () => {
  const cycle = new ReadCycle(), old = cycle.begin(), next = cycle.begin()
  assert.equal(old.current(), false)
  old.finish()
  assert.equal(cycle.pending, true)
  assert.equal(next.current(), true)
  cycle.invalidate()
  assert.equal(next.current(), false)
  assert.equal(cycle.pending, false)
})
