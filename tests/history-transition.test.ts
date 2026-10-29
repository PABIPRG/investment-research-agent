import test from 'node:test'
import assert from 'node:assert/strict'
import {
  alreadyTransitioned,
  beginHistoryTransition,
  finishHistoryTransition,
  isHistoryTransition,
} from '../product/ui/shell/history-transition.js'

test('同一会话完成转场后不再重复；用户再次选择时允许新转场', () => {
  beginHistoryTransition('session-a')
  assert.equal(isHistoryTransition('session-a'), true)
  finishHistoryTransition('session-a')
  assert.equal(isHistoryTransition('session-a'), false)
  assert.equal(alreadyTransitioned('session-a'), true)
  assert.equal(alreadyTransitioned('session-b'), false)
  beginHistoryTransition('session-a')
  assert.equal(isHistoryTransition('session-a'), true)
  assert.equal(alreadyTransitioned('session-a'), false)
  finishHistoryTransition('session-a')
})

import {
  historyTransition,
  updateHistoryOrigin,
  historyMotion,
} from '../product/ui/shell/history-transition.js'

test('历史之间保留当前屏幕起点；快速切换只保留最后一个目标', () => {
  const origin = { left: 90, top: 240, width: 96, height: 112, kind: 'response' as const }
  beginHistoryTransition('history-a', origin)
  const a = historyTransition('history-a')!
  assert.deepEqual(a.origin, origin)
  const moving = { ...origin, top: 360 }
  assert.equal(updateHistoryOrigin('history-a', a.revision, moving), true)
  assert.deepEqual(historyTransition('history-a')?.origin, moving)
  beginHistoryTransition('history-b', moving)
  finishHistoryTransition('history-a', a.revision)
  assert.equal(isHistoryTransition('history-b'), true)
  assert.equal(updateHistoryOrigin('history-a', a.revision, origin), false)
  finishHistoryTransition('history-b')
})

test('同一历史被重新选择时，旧动画结束不能撤销新转场', () => {
  beginHistoryTransition('same')
  const old = historyTransition('same')!
  beginHistoryTransition('same')
  const latest = historyTransition('same')!
  assert.notEqual(old.revision, latest.revision)
  finishHistoryTransition('same', old.revision)
  assert.equal(isHistoryTransition('same'), true)
  finishHistoryTransition('same', latest.revision)
  assert.equal(isHistoryTransition('same'), false)
})

test('历史回复区与问题卡片直接移动；欢迎页保留原转场，减少动态效果不旋转', () => {
  assert.deepEqual(historyMotion('response', 'response', false), { turn: false, duration: 420 })
  assert.deepEqual(historyMotion('question', 'question', false), { turn: false, duration: 420 })
  assert.deepEqual(historyMotion('response', 'question', false), { turn: false, duration: 420 })
  assert.deepEqual(historyMotion('question', 'response', false), { turn: false, duration: 420 })
  assert.deepEqual(historyMotion('welcome', 'response', false), { turn: true, duration: 560 })
  assert.deepEqual(historyMotion('response', 'question', true), { turn: false, duration: 0 })
})

test('离开页面后的过期呈现提示不会在重新打开时重放', (t) => {
  const clock = t.mock.method(Date, 'now', () => 1000)
  beginHistoryTransition('expired')
  clock.mock.mockImplementation(() => 9001)
  assert.equal(historyTransition('expired'), undefined)
  assert.equal(isHistoryTransition('expired'), false)
})
