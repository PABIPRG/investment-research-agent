import test from 'node:test'
import assert from 'node:assert/strict'
import { dockPoint, responseAnchor, type DockAnchor } from '../product/ui/shell/dock-model.js'
const start: DockAnchor = { key: 'process-1', turn: 1, kind: 'turn-process', visible: false }
const reply: DockAnchor = {
  key: 'reply-1',
  turn: 1,
  kind: 'assistant-step',
  part: 'response',
  visible: true,
}
test('零高度的本轮起点保持稳定，不追逐流式片段、后续步骤或完成状态', () => {
  for (const extra of [[], [reply], [reply, { ...reply, key: 'reply-2' }]]) {
    assert.equal(responseAnchor([start, ...extra])?.key, 'process-1')
  }
  assert.equal(
    responseAnchor([start, { ...reply, key: 'user-2', kind: 'user', turn: 2 }])?.key,
    'user-2',
  )
})
test('缺少过程起点时使用本轮首条回复；不会倒退到上一轮', () => {
  assert.equal(responseAnchor([reply, { ...reply, key: 'reply-2' }])?.key, 'reply-1')
  assert.equal(responseAnchor([reply, { ...start, key: 'process-2', turn: 2 }])?.key, 'process-2')
  assert.equal(responseAnchor([]), undefined)
})
test('滚动时位置直接限制在消息可视区，避开输入栏并保持横向边界', () => {
  const box = { bodyWidth: 1000, bodyHeight: 700, width: 96, height: 112, composerTop: 540 }
  assert.deepEqual(dockPoint({ ...box, x: 200, y: 120 }), { left: 92, top: 120 })
  assert.equal(dockPoint({ ...box, x: 200, y: -400 }).top, 8)
  assert.equal(dockPoint({ ...box, x: 200, y: 650 }).top, 416)
  assert.equal(dockPoint({ ...box, x: 20, y: 50 }).left, 4)
})
