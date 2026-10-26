import { test } from 'node:test'
import assert from 'node:assert/strict'
import { finishAttempt } from '../distribution/worker.js'
import type { Instance } from '../distribution/instance.js'
const config = { host: '127.0.0.1', port: 18722, worker_token: 'unit-worker-capability' } as Instance
const job = { attempt_id: 'unit-attempt', lease_token: 'unit-attempt-capability' }
const result = { status: 'succeeded', summary: 'unacceptable result' }
const response = (status: number, value: unknown) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

test('明确证据拒绝后复核同一租约并及时回写可读 failed', async t => {
  const calls: Array<{ url: string; body: any; token: string | null }> = []
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    calls.push({ url, body: JSON.parse(String(init.body)), token: new Headers(init.headers).get('X-Attempt-Token') })
    if (calls.length === 1) return response(409, { error: 'conflict', detail: 'result references unavailable evidence' })
    if (calls.length === 2) return response(200, { lease_until: Date.now() / 1000 + 30 })
    return response(200, { status: 'failed' })
  })
  assert.equal((await finishAttempt(config, job, result)).status, 'failed')
  assert.deepEqual(calls.map(c => c.url.split('/').at(-1)), ['finish', 'heartbeat', 'finish'])
  assert.ok(calls.every(c => c.token === job.lease_token))
  assert.equal(calls[2].body.status, 'failed'); assert.match(calls[2].body.error, /证据不可用/)
})

for (const [status, code, detail] of [
  [500, 'internal_error', 'result references unavailable evidence'],
  [403, 'forbidden', 'result references unavailable evidence'],
  [409, 'conflict', 'execution capability expired or revoked'],
  [409, 'conflict', 'result already committed with different content'],
  [409, 'conflict', 'unrecognized conflict'],
  [400, 'invalid_request', 'unknown validation'],
] as const) test(`HTTP ${status} ${detail} 保留不确定性，不写第二个结果`, async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return response(status, { error: code, detail }) })
  await assert.rejects(finishAttempt(config, job, result)); assert.equal(calls, 1)
})

test('网络或畸形响应不能推断拒绝，也不重放 finish', async t => {
  for (const failure of ['network', 'json']) {
    let calls = 0
    const mocked = t.mock.method(globalThis, 'fetch', async () => { calls++; if (failure === 'network') throw new TypeError('fetch failed'); return new Response('not-json', { status: 409 }) })
    await assert.rejects(finishAttempt(config, job, result)); assert.equal(calls, 1); mocked.mock.restore()
  }
})

test('校验拒绝后租约撤销，不提交 failed', async t => {
  const calls: string[] = []
  t.mock.method(globalThis, 'fetch', async (url: string) => {
    calls.push(url)
    return calls.length === 1 ? response(400, { error: 'invalid_request', detail: 'invalid execution result' })
      : response(409, { error: 'conflict', detail: 'execution capability expired or revoked' })
  })
  await assert.rejects(finishAttempt(config, job, result)); assert.equal(calls.length, 2); assert.ok(calls[1].endsWith('/heartbeat'))
})

test('停止或租约复核后取消，不再写终态', async t => {
  for (const stopAfter of [1, 2]) {
    let calls = 0
    const mocked = t.mock.method(globalThis, 'fetch', async () => {
      calls++
      return calls === 1 ? response(409, { error: 'conflict', detail: 'result binding or evidence missing' }) : response(200, { lease_until: Date.now() / 1000 + 30 })
    })
    await assert.rejects(finishAttempt(config, job, result, () => calls < stopAfter))
    assert.equal(calls, stopAfter); mocked.mock.restore()
  }
})

test('failed 提交回执不确定时不重放或重新执行', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls++
    if (calls === 1) return response(409, { error: 'conflict', detail: 'financial source unit and basis are unverified; judgement must be unknown' })
    if (calls === 2) return response(200, { lease_until: Date.now() / 1000 + 30 })
    throw new TypeError('response lost')
  })
  await assert.rejects(finishAttempt(config, job, result)); assert.equal(calls, 3)
})

test('正常提交保持原回执，不追加 heartbeat 或结果', async t => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; return response(200, { status: 'succeeded', revision: 3 }) })
  assert.deepEqual(await finishAttempt(config, job, result), { status: 'succeeded', revision: 3 }); assert.equal(calls, 1)
})

test('无有效租约回执时不追加失败写入', async t => {
  for (const lease of [{}, { lease_until: 0 }, { lease_until: 'tomorrow' }]) {
    let calls = 0
    const mocked = t.mock.method(globalThis, 'fetch', async () => { calls++; return calls === 1
      ? response(409, { error: 'conflict', detail: 'result references unavailable evidence' }) : response(200, lease) })
    await assert.rejects(finishAttempt(config, job, result)); assert.equal(calls, 2); mocked.mock.restore()
  }
})
