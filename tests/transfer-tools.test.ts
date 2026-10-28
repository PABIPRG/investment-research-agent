import test from 'node:test'
import assert from 'node:assert/strict'
import { createTransferTools, transferConfirmed } from '../product/chat/transfer-tools.js'
import { createTransferBridge } from '../product/ui/transfer-bridge.js'

test('legacy import requires native confirmation and binds session/receipt', async () => {
  const calls: { path: string; body: any }[] = []
  const previous = globalThis.fetch
  try {
    globalThis.fetch = async (url, options) => {
      const body = JSON.parse(String(options?.body))
      calls.push({ path: new URL(String(url)).pathname, body })
      return Response.json(String(url).endsWith('/prepare') ? {
        preview_id: 'TRV_synthetic', request_key: body.request_key, can_commit: true,
        summary: { holdings: { incoming: 1, conflicts: 0 } }, rules: { holdings: 'keep_local' },
        changes: { items: [], total: 0 }, warnings: [],
      } : { status: 'committed' })
    }
    const context: any = { agent: { session: { id: 'chat' } }, callId: 'call-one', signal: new AbortController().signal }
    let answer: any = { answers: [{ id: 'transfer-confirm', selected: ['确认导入'], custom: false }] }
    const tool = createTransferTools('http://127.0.0.1:18855/', 'synthetic', async () => answer)[1]
    await tool.execute({ upload_id: 'UPL_synthetic', selected: ['holdings'] }, context)
    assert.equal(calls.filter(x => x.path.endsWith('/commit')).length, 1)
    assert.equal(calls[0].body.session_id, 'chat')
    assert.equal(calls[0].body.request_key, calls[1].body.request_key)
    calls.length = 0
    answer = { answers: [{ id: 'transfer-confirm', selected: ['确认导入'], custom: true }] }
    await tool.execute({ upload_id: 'UPL_synthetic', selected: ['holdings'] }, context)
    assert(!calls.some(x => x.path.endsWith('/commit')))
    assert(calls.some(x => x.path.endsWith('/cancel')))
    await assert.rejects(async () => tool.execute({ upload_id: 'UPL_synthetic', selected: ['holdings'], path: '/private/data' }, context))
    assert(!transferConfirmed({ answers: [{ id: 'transfer-confirm', selected: ['确认导入', '暂不导入'] }] }))
  } finally { globalThis.fetch = previous }
})

test('settings import bridge binds owner session and rejects identity/path overrides', async () => {
  const bridge = createTransferBridge('http://127.0.0.1:18855/', 'synthetic')
  const previous = globalThis.fetch
  const calls: any[] = []
  const request = (body: any) => new Request('http://localhost/api/huohuo/transfer', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  try {
    globalThis.fetch = async (url, options) => {
      calls.push({ url: String(url), body: JSON.parse(String(options?.body)) })
      return Response.json({ items: [] })
    }
    assert.equal((await bridge(request({ operation: 'uploads' }))).status, 200)
    assert.equal(calls[0].body.session_id, 'ui-transfer-owner')
    for (const bad of [null, 1, 'text', [], { operation: 'uploads', principal: 'other' }, { operation: 'uploads', session_id: 'other' }, { operation: '../file' }])
      assert.equal((await bridge(request(bad))).status, 400)
    assert.equal(calls.length, 1)
    globalThis.fetch = async () => { throw Error('connection lost') }
    const result = await bridge(request({ operation: 'commit', preview_id: 'TRV_synthetic', request_key: 'same' }))
    assert.equal(result.status, 503)
    assert.match((await result.json() as any).detail, /结果暂不确定/)
  } finally { globalThis.fetch = previous }
})
