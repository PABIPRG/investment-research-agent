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
