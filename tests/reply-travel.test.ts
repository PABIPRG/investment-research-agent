import test from 'node:test'
import assert from 'node:assert/strict'
import { ReplyTurnTracker } from '../product/ui/shell/reply-travel.js'

test('新一轮移动一次，同一轮流式内容和滚动不重新触发', () => {
  const tracker = new ReplyTurnTracker()
  assert.equal(tracker.visit('chat', 1), false)
  assert.equal(tracker.visit('chat', 2), true)
  for (let i = 0; i < 8; i++) assert.equal(tracker.visit('chat', 2), false)
  assert.equal(tracker.visit('chat', 1), false)
  assert.equal(tracker.visit('chat', 2), false)
  assert.equal(tracker.visit('chat', 3), true)
})
test('切换会话、首次加载历史以及短暂缺少锚点不误当新回复', () => {
  const tracker = new ReplyTurnTracker()
  assert.equal(tracker.visit('a', 10), false)
  assert.equal(tracker.visit('a', undefined), false)
  assert.equal(tracker.visit('a', 11), true)
  assert.equal(tracker.visit('b', 12), false)
  assert.equal(tracker.visit('b', 13), true)
})
