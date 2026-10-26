import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'node:http'
import { createQueryBridge } from '../product/ui/bridge.js'

const id = '11111111-1111-4111-8111-111111111111'
test('查询桥只允许固定 GET 与严格参数，不转发浏览器身份或任意地址', async () => {
  const seen: { url?: string; headers: Record<string, unknown> }[] = []
  const server = createServer((req, res) => {
    seen.push({ url: req.url, headers: req.headers })
    res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ status: 'queued' }))
  })
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r))
  const address = `http://127.0.0.1:${(server.address() as { port: number }).port}`
  try {
    const bridge = createQueryBridge(address, 'server-only')
    for (const [path, target] of [
      ['executions', '/executions'], ['execution', `/executions/${id}`],
      ['events', `/executions/${id}/events`], ['evidence', `/executions/${id}/evidence`],
    ]) {
      const response = await bridge(new Request(`http://dsh.internal/api/huohuo/${path}${path === 'executions' ? '' : `?id=${id}`}`, {
        headers: { Authorization: 'Bearer attacker', Cookie: 'private', Origin: 'http://untrusted.example' },
      }))
      assert.equal(response.status, 200); assert.equal(response.headers.get('cache-control'), 'no-store')
      assert.equal(seen.at(-1)?.url, target)
      assert.equal(seen.at(-1)?.headers.authorization, 'Bearer server-only')
      assert.equal(seen.at(-1)?.headers.cookie, undefined); assert.equal(seen.at(-1)?.headers.origin, undefined)
    }
    for (const path of ['executions?id=x', 'execution', `execution?id=${id}&id=${id}`, `execution?id=${id}&url=http://evil`,
      'execution?id=../worker/claim', 'execution?id=%252e%252e', 'worker/claim', `evidence?id=${id}/cancel`]) {
      assert.ok((await bridge(new Request(`http://dsh.internal/api/huohuo/${path}`))).status >= 400)
    }
    assert.equal((await bridge(new Request('http://dsh.internal/api/huohuo/executions', { method: 'POST' }))).status, 405)
    assert.equal(seen.length, 4)
    for (const invalid of ['https://127.0.0.1:99', address + '/extra', address + '/?token=x', address + '/#x', 'http://example.com:80']) {
      assert.throws(() => createQueryBridge(invalid, 'token'))
    }
  } finally { await new Promise<void>(r => server.close(() => r())) }
})

test('后台异常不泄漏信息、不跟随重定向，未知任务保留 404', async () => {
  let mode = 'missing'; let redirects = 0
  const server = createServer((req, res) => {
    if (req.url === '/secret') { redirects++; res.end('secret'); return }
    if (mode === 'redirect') { res.writeHead(302, { Location: '/secret' }); res.end(); return }
    if (mode === 'malformed') { res.end('private internal error'); return }
    if (mode === 'oversize') { res.end('x'.repeat(2_000_001)); return }
    if (mode === 'large-list') { res.end(JSON.stringify({ executions: Array.from({ length: 50 }, () => ({ result: { summary: '研'.repeat(20000) } })) })); return }
    res.writeHead(404, { 'Content-Type': 'application/json' }); res.end('{"error":"not_found"}')
  })
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r))
  const bridge = createQueryBridge(`http://127.0.0.1:${(server.address() as {port:number}).port}`, 'private-token')
  const request = () => bridge(new Request(`http://dsh.internal/api/huohuo/execution?id=${id}`))
  try {
    assert.equal((await request()).status, 404)
    for (mode of ['redirect', 'malformed', 'oversize']) {
      const response = await request(); assert.ok(response.status >= 500)
      assert.doesNotMatch(await response.text(), /private|secret|token/)
    }
    assert.equal(redirects, 0)
    mode = 'large-list'
    const large = await bridge(new Request('http://dsh.internal/api/huohuo/executions'))
    assert.equal(large.status, 200)
    assert.equal((await large.json()).executions.length, 50)
  } finally { await new Promise<void>(r => server.close(() => r())) }
  assert.equal((await request()).status, 503)
})
