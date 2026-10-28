import test from 'node:test'
import assert from 'node:assert/strict'
import { createSecurityBridge } from '../product/ui/security-bridge.js'
const make = (body: unknown) =>
  new Request('http://localhost/api/huohuo/security-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
test('证券桥只允许固定搜索语义，拒绝主体和目标注入', async () => {
  const bridge = createSecurityBridge('http://127.0.0.1:18830', 'fixture-token')
  for (const body of [
    { query: '茅台', url: 'https://example.invalid' },
    { query: '茅台', principal: 'other' },
    { query: '' },
    [],
    { query: 'a'.repeat(101) },
  ])
    assert.equal((await bridge(make(body))).status, 400)
  assert.throws(() => createSecurityBridge('https://example.invalid', 'x'))
})
test('证券桥复用已有本机接口，透传 stale 而不改写为可用', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(String(url), 'http://127.0.0.1:18830/entities/search')
      assert.equal(options?.body, JSON.stringify({ query: '茅台' }))
      return Response.json({ status: 'stale', usable_for_confirmation: false, candidates: [] })
    }
    const bridge = createSecurityBridge('http://127.0.0.1:18830', 'fixture-token')
    assert.equal((await (await bridge(make({ query: ' 茅台 ' }))).json()).status, 'stale')
    globalThis.fetch = async () => {
      throw Error('offline')
    }
    assert.equal((await bridge(make({ query: '茅台' }))).status, 503)
  } finally {
    globalThis.fetch = original
  }
})
