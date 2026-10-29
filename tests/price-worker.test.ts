import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { runAttempt } from '../distribution/worker.js'
import type { Instance } from '../distribution/instance.js'
test('已核验价格任务走内部程序接口，不初始化DSH或读取模型配置', async () => {
  const calls: string[] = [], observations: string[] = []
  const server = createServer((req, res) => {
    calls.push(req.url || '')
    assert.equal(req.headers.authorization, 'Bearer worker-only')
    assert.equal(req.headers['x-attempt-token'], 'attempt-only')
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({status: 'succeeded'}))
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  try {
    const address = server.address() as {port: number}
    const config = {host: '127.0.0.1', port: address.port, worker_token: 'worker-only'} as Instance
    const result = await runAttempt(config, {price_rule: true, attempt_id: 'attempt', lease_token: 'attempt-only'}, new AbortController().signal, event => observations.push(event.kind))
    assert.equal(result, 'completed')
    assert.deepEqual(calls, ['/worker/attempts/attempt/price-run'])
    assert.deepEqual(observations, ['program.price-rule'])
  } finally { await new Promise<void>(resolve => server.close(() => resolve())) }
})
