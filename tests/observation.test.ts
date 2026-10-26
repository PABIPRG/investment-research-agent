import test from 'node:test'
import assert from 'node:assert/strict'
import { activityObservation } from '../distribution/observation.js'

test('观察摘要不传播提示词、请求参数或工具完整返回内容', () => {
  const secret = 'must-not-leak'
  const inputs = [
    { type: 'system/message', data: { message: { content: secret + ' HUOHUO_BOUNDED_QUOTE_V1' } } },
    { type: 'request/header', data: { header: { config: { provider: 'fixture', model: 'demo', secret }, tools: [{ name: 'quote', secret }] } } },
    { type: 'tool/call', data: { name: 'quote', callId: 'call', arguments: secret } },
    { type: 'tool/result', data: { message: { toolCallId: 'call', content: [{ type: 'text', text: JSON.stringify({ evidence_id: 'e1', status: 'ok', secret }) }] } } },
    { type: 'assistant/message', data: { message: { content: secret } } },
  ]
  const values = inputs.map(activityObservation)
  assert.equal(JSON.stringify(values).includes(secret), false)
  assert.equal(values[0]?.skill_visible, true)
  assert.deepEqual(values[1]?.tools, ['quote'])
  assert.equal(values[3]?.evidence_id, 'e1')
  assert.equal(values[4], undefined)
})
test('工具错误与 turn 结束原因分别保留，不从文本猜成功', () => {
  assert.equal(activityObservation({ type: 'tool/result', data: { message: { isError: true, content: [] } } })?.is_error, true)
  assert.equal(activityObservation({ type: 'turn/end', data: { reason: { kind: 'max-tokens' } } })?.reason, 'max-tokens')
})
