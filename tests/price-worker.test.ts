import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { runAttempt, type RuntimeFactory } from '../distribution/worker.js'
import type { Instance } from '../distribution/instance.js'
test('已核验价格任务走内部程序接口，不初始化DSH或读取模型配置', async () => {
  const calls: string[] = [], observations: string[] = []
  const server = createServer((req, res) => {
    calls.push(req.url || '')
    assert.equal(req.headers.authorization, 'Bearer worker-only')
    assert.equal(req.headers['x-attempt-token'], 'attempt-only')
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify(req.url?.endsWith('/model-admission')
      ? {policy: 'hook-model-gate-v1', execution_id: 'execution', attempt_id: 'attempt', phase: 'prepare', mode: 'program', reason: 'deterministic_condition'}
      : {status: 'succeeded'}))
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  try {
    const address = server.address() as {port: number}
    const config = {host: '127.0.0.1', port: address.port, worker_token: 'worker-only'} as Instance
    const factory: RuntimeFactory = () => { throw Error('程序价格检查不应构造模型') }
    const result = await runAttempt(config, {price_rule: true, execution_id: 'execution', attempt_id: 'attempt', lease_token: 'attempt-only'}, new AbortController().signal, event => observations.push(event.kind), factory)
    assert.equal(result, 'completed')
    assert.deepEqual(calls, ['/worker/attempts/attempt/model-admission', '/worker/attempts/attempt/program-run'])
    assert.deepEqual(observations, ['program.price-rule'])
  } finally { await new Promise<void>(resolve => server.close(() => resolve())) }
})

test('程序取数超过心跳周期时续租，不构造模型', async () => {
  let heartbeats = 0
  const server = createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json')
    if (req.url?.endsWith('/model-admission')) {
      res.end(JSON.stringify({policy: 'hook-model-gate-v1', execution_id: 'execution', attempt_id: 'attempt', phase: 'prepare', mode: 'program', reason: 'deterministic_condition'}))
    } else if (req.url?.endsWith('/heartbeat')) {
      heartbeats++; res.end(JSON.stringify({lease_until: Date.now() / 1000 + 30}))
    } else {
      setTimeout(() => res.end(JSON.stringify({status: 'succeeded'})), 5500)
    }
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  try {
    const config = {host: '127.0.0.1', port: (server.address() as {port:number}).port, worker_token: 'synthetic'} as Instance
    const factory: RuntimeFactory = () => { throw Error('慢取数不应启动模型') }
    assert.equal(await runAttempt(config, {execution_id:'execution',attempt_id:'attempt',lease_token:'synthetic'}, new AbortController().signal, undefined, factory), 'completed')
    assert.ok(heartbeats >= 1, '取数期间必须保持正式 attempt 租约')
  } finally { await new Promise<void>(resolve => server.close(() => resolve())) }
})
