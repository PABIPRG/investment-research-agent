import test from 'node:test'
import assert from 'node:assert/strict'
import { decisionContext, contactOutcome } from '../product/ui/mandates/readable-model.js'
import { evidenceTitle, researchFinding } from '../product/ui/shared/evidence-display.js'
import type { MandateView, ContactDecision } from '../product/ui/mandates/model.js'
import { marketQuoteRows } from '../product/ui/shared/market-evidence.js'
import type { Evidence } from '../product/ui/model.js'
const decision = { job_id: 'job1', evidence_ref: 'a' } as ContactDecision
const view = {
  evidence: [{ evidence_id: 'a' }, { evidence_id: 'b' }],
  results: [
    {
      job_id: 'job1',
      stale: false,
      structured_result: { evidence_ids: ['a'], summary: 'result1' },
    },
    { job_id: 'job2', stale: false, structured_result: { evidence_ids: ['b'], summary: 'other' } },
  ],
} as MandateView
test('决定仅显示明确关联的资料与结果，不混入另一轮证据', () => {
  const linked = decisionContext(view, decision)
  assert.equal(linked.result?.summary, 'result1')
  assert.deepEqual(
    linked.evidence.map((e) => e.evidence_id),
    ['a'],
  )
  assert.equal(decisionContext(view, { ...decision, evidence_ref: 'missing' }).result, undefined)
  assert.deepEqual(decisionContext(view, { ...decision, evidence_ref: 'missing' }).evidence, [])
  assert.equal(
    decisionContext(
      { ...view, results: view.results?.map((r) => ({ ...r, stale: true })) },
      decision,
    ).result,
    undefined,
  )
})
test('相同任务存在多份结果且无法唯一绑定时，不猜测判断理由', () => {
  const multiple = { ...view, results: [...view.results!, view.results![0]] }
  assert.equal(decisionContext(multiple, decision).result, undefined)
  assert.equal(
    decisionContext(view, { ...decision, job_id: undefined, evidence_ref: undefined }).result,
    undefined,
  )
})
test('资料标题呈现报告期与指标，单位未知不转换成金额', () => {
  assert.equal(
    evidenceTitle({
      evidence_id: 'a',
      attempt_id: 'x',
      status: 'ok',
      source: 'akshare.stock_financial_abstract',
      values: { metric: '营业总收入', period: '20260630' },
    }),
    '2026 年 6 月 30 日 · 营业总收入',
  )
  const finding = researchFinding({
    summary: '已完成',
    judgements: { notable_change: { judgement: 'unknown', reason: '单位尚未核验' } },
  })
  assert.equal(finding.detail, '单位尚未核验')
  assert.match(finding.title, /不能判断/)
  assert.match(contactOutcome('send'), /送达状态/)
  assert.match(researchFinding(null).title, /尚无/)
})

test('定时交付的批次引用只展开同一任务唯一匹配的结果资料', () => {
  const batchView = {
    ...view,
    results: view.results!.map((r, i) => ({ ...r, evidence_batch_id: `batch${i + 1}` })),
  }
  const timed = { ...decision, evidence_ref: 'batch1' }
  const linked = decisionContext(batchView, timed)
  assert.equal(linked.result?.summary, 'result1')
  assert.deepEqual(
    linked.evidence.map((e) => e.evidence_id),
    ['a'],
  )
  assert.deepEqual(decisionContext(batchView, { ...timed, evidence_ref: 'batch2' }).evidence, [])
  assert.deepEqual(
    decisionContext(
      { ...batchView, results: batchView.results.map((r) => ({ ...r, stale: true })) },
      timed,
    ).evidence,
    [],
  )
  assert.deepEqual(
    decisionContext({ ...batchView, results: [...batchView.results, batchView.results[0]] }, timed)
      .evidence,
    [],
  )
})

test('行情证据保留名称、原始零值、时间与单位，不把未知补成数字', () => {
  const row = {
    evidence_id: 'synthetic-quote',
    attempt_id: 'synthetic-attempt',
    status: 'ok',
    source: '明确合成报价',
    scope: { operation: 'market_quote' },
    values: {
      items: [
        {
          name: '合成证券',
          price: 110,
          pct_change: 0,
          previous_close: null,
          time_known: true,
          as_of: '2026-10-28T03:42:01+00:00',
          stale: false,
          units: { price: 'CNY/share', pct_change: '%' },
        },
      ],
    },
  } as Evidence
  const quote = marketQuoteRows(row)[0]
  assert.equal(quote.name, '合成证券')
  assert.equal(quote.facts[0].label, '报价（元/股）')
  assert.equal(quote.facts[1].value, '—')
  assert.equal(quote.facts[2].value, '0')
  assert.equal(quote.stale, false)
  row.values!.items![0].units = { price: 'unknown' }
  row.values!.items![0].time_known = false
  const unknown = marketQuoteRows(row)[0]
  assert.match(unknown.facts[0].label, /单位未核验/)
  assert.equal(unknown.asOf, undefined)
})
