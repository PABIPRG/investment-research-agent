import test from 'node:test'
import assert from 'node:assert/strict'
import { resultFromActivity, runtimeEnvironment } from '../distribution/worker.js'
import type { Instance } from '../distribution/instance.js'

const success = { status: 'succeeded', execution_id: 'job', evidence_ids: ['real-evidence'] }
const message = (turn = 1, interrupted = false) => ({ type: 'assistant/message', data: { turn, interrupted, message: { content: [{ type: 'text', text: JSON.stringify(success) }] } } })
const end = (kind: string, turn = 1) => ({ type: 'turn/end', data: { turn, reason: { kind } } })
test('完成的同一 turn 才能接受结果', () => assert.deepEqual(resultFromActivity([message(), end('completed')]), success))
test('合法成功 JSON 不能掩盖截断、中断、失败或缺少终止事件', () => {
  for (const kind of ['max-tokens', 'aborted', 'error', 'interrupted']) {
    assert.equal((resultFromActivity([message(), end(kind)]) as any).status, 'failed')
  }
  assert.equal((resultFromActivity([message()]) as any).status, 'failed')
  assert.equal((resultFromActivity([message(1, true), end('completed')]) as any).status, 'failed')
  assert.equal((resultFromActivity([message(1), end('completed', 2)]) as any).status, 'failed')
})
test('运行时不继承未列入白名单的父环境', () => {
  process.env.HUOHUO_TEST_SECRET = 'do-not-inherit'
  try { assert.equal(runtimeEnvironment({ dsh_home: '/tmp/test' } as Instance).HUOHUO_TEST_SECRET, undefined) }
  finally { delete process.env.HUOHUO_TEST_SECRET }
})
