import test from 'node:test'
import assert from 'node:assert/strict'
import { createDeliverableTools } from '../product/chat/deliverable-tools.js'
import { createDeliverableDownload } from '../product/ui/deliverables/bridge.js'
import { deliveryRecorder } from '../product/chat/deliverable-events.js'

const id = 'a'.repeat(64)
const base = 'http://127.0.0.1:18930'
const exec = () => ({ agent: { session: { id: 'chat' } }, callId: 'c1', signal: new AbortController().signal }) as any

test('成果工具绑定可信会话和调用，不开放路径；仅成功回执登记交付', async (t) => {
  const previous = globalThis.fetch
  t.after(() => { globalThis.fetch = previous })
  const calls: any[] = [], delivered: any[] = []
  globalThis.fetch = async (url, init) => {
    calls.push([url, JSON.parse(init!.body as string)])
    return Response.json({ id, file_path: '/workspace/file.xlsx' })
  }
  const [tool, read] = createDeliverableTools(base, 'test-secret', (_exec, file) => delivered.push(file))
  const spec = { format: 'json', title: '研究', content_kind: 'model_analysis', evidence_ids: [], limitations: '未核验', tables: [] }
  assert.equal((await tool.execute(spec, exec()) as any).ok, true)
  assert.deepEqual(calls[0][1], { session_id: 'chat', call_id: 'c1', spec })
  assert.equal(delivered.length, 1)
  await assert.rejects(tool.execute({ ...spec, path: '/tmp/secrets' }, exec()))
  await assert.rejects(tool.execute(spec, { ...exec(), agent: undefined }))
  await read.execute({ id }, exec())
  assert.deepEqual(calls[1][1], { session_id: 'chat', id })
  globalThis.fetch = async () => Response.json({ detail: '失败' }, { status: 400 })
  assert.equal((await tool.execute(spec, exec()) as any).ok, false)
  assert.equal(delivered.length, 2)
  globalThis.fetch = async () => { throw Error('connection interrupted') }
  const unknown = await tool.execute(spec, exec()) as any
  assert.equal(unknown.error, 'submission_unknown')
  assert.equal(unknown.source_call_id, 'c1')
  assert.equal(delivered.length, 2)
  globalThis.fetch = async () => Response.json({ error: 'internal_error' }, { status: 500 })
  assert.equal((await tool.execute(spec, exec()) as any).error, 'submission_unknown')
})

test('下载只读已认证成果，事件坐标绑定原会话；拒绝额外参数和任意路径', async (t) => {
  const previous = globalThis.fetch
  t.after(() => { globalThis.fetch = previous })
  const requests: any[] = []
  globalThis.fetch = async (_url, init) => {
    requests.push(JSON.parse(init!.body as string))
    return new Response('abc', { headers: { 'Content-Length': '3', 'Content-Disposition': "attachment; filename*=UTF-8''test.csv", 'Content-Type': 'text/csv' } })
  }
  const bridge = createDeliverableDownload(base, 'never-render-token', async (session, seq, index) => {
    assert.deepEqual([session, seq, index], ['chat', 42, 0])
    return `/workspace/.huohuo-deliverables/${id}/test.csv`
  })
  const request = (query: string) => new Request(`http://localhost/api/huohuo/deliverables/download?${query}`)
  const result = await bridge(request('sessionId=chat&seq=42&index=0'))
  assert.equal(result.status, 200)
  assert.equal(await result.text(), 'abc')
  assert.deepEqual(requests, [{ id, part: 'file', session_id: 'chat' }])
  assert.equal(result.headers.get('Cache-Control'), 'no-store')
  assert.equal(result.headers.get('Authorization'), null)
  for (const query of ['id=../business.sqlite', `id=${id}&path=/tmp/a`, `id=${id}&id=${id}`, `id=${id}&sessionId=chat`, 'sessionId=chat&seq=-1&index=0', `id=${id}&part=secrets`]) {
    assert.equal((await bridge(request(query))).status, 400)
  }
  globalThis.fetch = async () => new Response('truncated', { headers: { 'Content-Length': '99' } })
  assert.equal((await bridge(request(`id=${id}`))).status, 502)
  globalThis.fetch = async () => { throw Error('private failure /tmp/secret') }
  const failure = await bridge(request(`id=${id}`))
  assert.equal(failure.status, 503)
  assert.ok(!(await failure.text()).includes('secret'))
})

test('交付适配只发布自身成功成果，不信任任意工具输出，遵守 DSH 轮次协议', () => {
  let listener: any
  const events: any[] = []
  const context = {
    on: (_event: string, callback: any) => { listener = callback },
    sessionProjections: { stateOf: () => ({ lastTurn: 2, openTurnStartSeq: 1 }) },
  }
  const record = deliveryRecorder(context as any)
  const run = exec()
  run.agent.session.append = (...args: any[]) => events.push(args)
  const file = { id, filename: 'a.csv', file_path: '/files/a.csv', metadata_path: '/files/交付说明.json', content_kind: 'evidence', bytes: 20 } as any
  listener(run, { isError: false })
  assert.equal(events.length, 0)
  record(run, file); listener(run, { isError: true })
  assert.equal(events.length, 0)
  record(run, file); listener(run, { isError: false })
  assert.equal(events.length, 1)
  assert.equal(events[0][0], 'deliverables/presented')
  assert.equal(events[0][1].turn, 2)
  assert.deepEqual(events[0][1].files.map((f: any) => f.path), [file.file_path, file.metadata_path])
  listener(run, { isError: false }); assert.equal(events.length, 1)
})
