import assert from 'node:assert/strict'
import test from 'node:test'
import { apply } from '../product/chat/guard.js'

test('聊天允许产品原生 Skill，拒绝外部 Skill 和执行工具', () => {
  let guard: (call: any) => unknown = () => 'not installed'
  apply({ tools: { guard: (fn: typeof guard) => { guard = fn } }, on() {} } as any)
  for (const name of ['huohuo-research-chat', 'huohuo-mandates', 'huohuo-investment-facts', 'huohuo-notifications']) {
    assert.equal(guard({ name: 'skill', arguments: { name } }), undefined)
  }
  for (const name of ['user-secret-skill', '../outside', 'huohuo-bounded-quote']) {
    assert.ok(guard({ name: 'skill', arguments: { name } }))
  }
  assert.ok(guard({ name: 'skill', arguments: { name: 'huohuo-research-chat', path: '/tmp' } }))
  for (const name of ['bash', 'write', 'web_fetch', 'subagent', 'run_code', 'present']) assert.ok(guard({ name, arguments: {} }))
})
