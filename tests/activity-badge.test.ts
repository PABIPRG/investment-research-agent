import test from 'node:test'
import assert from 'node:assert/strict'
import {
  rememberActivity,
  unseenActivity,
  type ActivityRecord,
} from '../product/ui/activity/model.js'
const row: ActivityRecord = {
  decision_id: 'one',
  mandate_id: 'm',
  channel: 'app',
  status: 'delivered',
  updated_at: 10,
}
test('新动态按决定去重，不把多个渠道当成多条待办', () => {
  const items = [row, { ...row, channel: 'email', status: 'accepted' }]
  assert.equal(unseenActivity(items, {}), 1)
  const seen = rememberActivity({}, items)
  assert.equal(unseenActivity([...items].reverse(), seen), 0)
  assert.equal(unseenActivity([...items, { ...row, decision_id: 'two' }], seen), 1)
})
test('实际展示过的版本才消除角标；新的投递状态重新提示', () => {
  const seen = rememberActivity({}, [row])
  const changed = { ...row, status: 'failed', updated_at: 12 }
  assert.equal(unseenActivity([changed], seen), 1)
  assert.equal(unseenActivity([row], rememberActivity(seen, [])), 0)
  assert.equal(unseenActivity([changed], rememberActivity(seen, [changed])), 0)
  assert.equal(unseenActivity([], seen), 0)
})
