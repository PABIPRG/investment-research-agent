import test from 'node:test'
import assert from 'node:assert/strict'
import { latestFailedTurn } from '../product/ui/shell/companion-feedback.js'
import { companionMotion } from '../product/ui/companion-state.js'

test('只响应最新一轮真实失败，旧失败不影响新的回答', () => {
  assert.equal(latestFailedTurn([{ turn: 1, failed: true }]), 1)
  assert.equal(
    latestFailedTurn([
      { turn: 1, failed: true },
      { turn: 2, failed: false },
    ]),
    undefined,
  )
  assert.equal(
    latestFailedTurn([
      { turn: 2, failed: false },
      { turn: 2, failed: true },
    ]),
    2,
  )
  assert.equal(latestFailedTurn([]), undefined)
})
test('失败表达让位于用户输入、运行及待确认状态', () => {
  assert.equal(companionMotion({ failed: true }), 'sigh')
  assert.equal(companionMotion({ failed: true, draft: '继续' }), 'listening')
  assert.equal(companionMotion({ failed: true, running: true }), 'thinking')
  assert.equal(companionMotion({ failed: true, pending: true }), 'awaiting_reply')
  assert.equal(companionMotion({ failed: false }), 'idle')
})
