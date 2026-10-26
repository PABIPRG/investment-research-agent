import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'node:http'
import { createChatTools, chatToolNames } from '../product/chat/tools.js'

test('聊天工具限定请求、稳定幂等和可核对的冲突', async () => {
  const seen: any[] = []
  const server = createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk)
    seen.push({ url: req.url, token: req.headers.authorization, body: chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : undefined })
    res.writeHead(req.url?.endsWith('/cancel') ? 409 : 200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(req.url?.endsWith('/cancel') ? { error: 'conflict', detail: 'revision conflict' } : { status: 'queued', execution_id: 'id' }))
  })
  await new Promise<void>(r => server.listen(Number(process.env.HUOHUO_CHAT_TEST_PORT ?? 0), '127.0.0.1', r))
  try {
    const port = (server.address() as {port:number}).port
    const tools = createChatTools(`http://127.0.0.1:${port}`, 'user-only')
    assert.deepEqual(tools.map(t => t.name), chatToolNames)
    const call = (name: string, args: unknown, session = 'a') => tools.find(t => t.name === name)!.execute(args, {
      callId: 'call-one', agent: { session: { id: session } }, signal: new AbortController().signal,
    } as any)
    const searched:any = await call('search_securities', {query:'科士达'})
    assert.equal(seen.pop().url, '/entities/search')
    assert.equal(searched.ok,true)
    await assert.rejects(() => call('search_securities', {query:'科士达',url:'https://evil.invalid'}))
    const args = { code: '600519', question: '请查看当前报价' }
    await call('submit_quote_research', args); await call('submit_quote_research', args)
    assert.equal(seen[0].body.request_key, seen[1].body.request_key)
    await call('submit_quote_research', args, 'b')
    assert.notEqual(seen[0].body.request_key, seen[2].body.request_key)
    assert.deepEqual(seen[0].body.scope, { entity_id: 'SEC:CN:A:600519', exchange: 'SSE', operation: 'quote_snapshot' })
    assert.equal(seen[0].token, 'Bearer user-only')
    await assert.rejects(() => call('submit_quote_research', { ...args, code: '399001' }))
    await assert.rejects(() => call('submit_quote_research', { ...args, principal: 'other' }))
    await assert.rejects(() => call('get_research', { execution_id: '../worker/claim' }))
    const conflict: any = await call('cancel_research', { execution_id: '11111111-1111-4111-8111-111111111111', expected_revision: 1 })
    assert.equal(conflict.error, 'conflict'); assert.equal(conflict.http_status, 409)
    assert.match(conflict.detail, /revision/)
  } finally { await new Promise<void>(r => server.close(() => r())) }
})
