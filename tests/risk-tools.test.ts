import test from 'node:test'
import assert from 'node:assert/strict'
import { createRiskTools } from '../product/chat/risk-tools.js'
import { createInvestmentBridge } from '../product/ui/investment-bridge.js'
const exec = { agent: { session: { id: 'risk-session' } }, callId: 'risk-call', signal: new AbortController().signal } as any
const bank = ['horizon', 'loss_tolerance', 'goal'].map(qid => ({ qid, title: qid, options: ['选项甲', '选项乙'] }))
const profile = { label: '稳健型', score: 6, max_score: 15, answers: bank.map(q => ({ qid: q.qid, label: '选项乙' })) }
const preview = { preview_id: '00000000-0000-4000-8000-000000000001', after: { risk_profile: profile } }
const answers = { answers: bank.map(q => ({ id: 'risk-' + q.qid, selected: ['选项乙'] })) }
test('问卷仅取原生选项并再次确认，原生调用身份不同', async () => {
  const old = globalThis.fetch, calls: any[] = [], asks: any[] = []
  try {
    globalThis.fetch = async (url, init) => {
      calls.push({ path: new URL(String(url)).pathname, body: init?.body && JSON.parse(String(init.body)) })
      return Response.json(String(url).endsWith('/preview') ? preview : init?.method === 'POST' ? { saved: true } : { risk_questionnaire: { quick: bank } })
    }
    const tool = createRiskTools('http://127.0.0.1:18870', 'fixture', async (_q, e) => {
      asks.push(e.callId)
      return asks.length === 1 ? answers : { answers: [{ id: 'business-confirm', selected: ['确认执行'] }] }
    })[0]
    assert.equal((await tool.execute({ tier: 'quick' }, exec) as any).data.saved, true)
    assert.notEqual(asks[0], asks[1])
    assert.deepEqual(calls[1].body, { command: 'risk_profile', payload: { tier: 'quick', answers: bank.map(q => ({ qid: q.qid, option: 1 })) } })
    assert.deepEqual(calls[2].body, { preview_id: preview.preview_id, request_key: preview.preview_id })
  } finally { globalThis.fetch = old }
})
test('取消、自由文字、重复和迟到答案不保存', async () => {
  const old = globalThis.fetch
  try {
    let writes = 0
    globalThis.fetch = async (_url, init) => { if (init?.method === 'POST') writes++; return Response.json({ risk_questionnaire: { quick: bank } }) }
    const cases = [{ pending: true }, { answers: [] }, { answers: [answers.answers[0], answers.answers[0], answers.answers[2]] }, { answers: answers.answers.map(a => ({ ...a, custom: '自己说的' })) }]
    for (const value of cases) {
      const t = createRiskTools('http://127.0.0.1:18870', 'fixture', async () => value)[0]
      const result: any = await t.execute({ tier: 'quick' }, exec)
      assert.ok(result.saved === false || result.ok === false)
    }
    const abort = new AbortController()
    const t = createRiskTools('http://127.0.0.1:18870', 'fixture', async () => { abort.abort(); return answers })[0]
    assert.equal((await t.execute({ tier: 'quick' }, { ...exec, signal: abort.signal }) as any).saved, false)
    assert.equal(writes, 0)
  } finally { globalThis.fetch = old }
})
test('提交未知保留原预览且不自动重试', async () => {
  const old = globalThis.fetch
  try {
    let asks = 0, commits = 0
    globalThis.fetch = async (url) => {
      if (String(url).endsWith('/commit')) { commits++; throw Error('offline') }
      return Response.json(String(url).endsWith('/preview') ? preview : { risk_questionnaire: { quick: bank } })
    }
    const t = createRiskTools('http://127.0.0.1:18870', 'fixture', async () => ++asks === 1 ? answers : { answers: [{ id: 'business-confirm', selected: ['确认执行'] }] })[0]
    const result: any = await t.execute({ tier: 'quick' }, exec)
    assert.equal(result.error, 'submission_unknown'); assert.equal(result.preview_id, preview.preview_id); assert.equal(commits, 1)
  } finally { globalThis.fetch = old }
})
test('网页回执核对仅转发固定GET，拒绝身份覆盖', async () => {
  const old = globalThis.fetch
  try {
    let requests = 0
    globalThis.fetch = async (url, init) => {
      requests++; assert.equal(new URL(String(url)).pathname, '/investment/previews/' + preview.preview_id)
      assert.equal(init?.method, 'GET'); assert.equal(init?.body, undefined)
      return Response.json({ receipt: { saved: true } })
    }
    const bridge = createInvestmentBridge('http://127.0.0.1:18870', 'fixture')
    const request = (body: any) => new Request('http://localhost/api/huohuo/investment-command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    assert.equal((await bridge(request({ action: 'inspect-preview', preview_id: preview.preview_id }))).status, 200)
    assert.equal((await bridge(request({ action: 'inspect-preview', preview_id: preview.preview_id, principal: 'other' }))).status, 400)
    assert.equal((await bridge(request({ action: 'inspect-preview', preview_id: '../../worker' }))).status, 400)
    assert.equal(requests, 1)
  } finally { globalThis.fetch = old }
})
