import test from 'node:test'
import assert from 'node:assert/strict'
import { arrivalStatus, canRetryBaseline } from '../product/ui/shell/arrival-model.js'
import type { MandateView } from '../product/ui/mandates/model.js'
const view = (extra: Record<string, unknown> = {}) =>
  ({
    mandate: { status: 'tracking' },
    executions: [],
    baseline: null,
    monitoring: { enabled: true },
    requires_comparison_baseline: false,
    execution_mode: 'program_price',
    ...extra,
  }) as unknown as MandateView
test('纯价格委托无比较基准也显示继续检查，不提示重建基准', () => {
  const item = view({ decisions: [{ condition_result: 'unmet' }] })
  assert.match(arrivalStatus(item).title, /未到价/)
  assert.equal(canRetryBaseline(item), false)
})
test('失败展示实际原因与历史成功保留，来源故障不冒充到价判断', () => {
  const failed = { status: 'failed', result: { error: '模型输出不符合研究结果 JSON 契约' } }
  const item = view({ executions: [failed, { status: 'succeeded' }] })
  assert.match(arrivalStatus(item).detail, /JSON 契约/)
  assert.match(arrivalStatus(item).detail, /成功/)
  assert.match(
    arrivalStatus(
      view({ source_check: { status: 'unavailable', detail: 'market_source_stale_or_partial' } }),
    ).detail,
    /过期|缺失/,
  )
  assert.equal(
    canRetryBaseline(view({ requires_comparison_baseline: true, executions: [failed] })),
    true,
  )
})


test('到时提醒和定时交付不要求研究基准，首页按真实日程展示', () => {
  for (const mode of ['due_reminder', 'scheduled_delivery', 'periodic_check']) {
    const item = view({execution_mode: 'research', revision: {contact_policy: {mode}},
      schedules: [{enabled: true, next_due_at: '2026-10-30T08:00:00Z', timezone: 'Asia/Shanghai'}]})
    const state = arrivalStatus(item)
    assert.doesNotMatch(state.title + state.detail, /第一份研究|研究基准/)
    assert.match(state.detail, /16:00/)
    assert.equal(canRetryBaseline(item), false)
  }
})
test('没有保存日程时不伪造下次时间，条件研究仍可等待第一份结果', () => {
  assert.match(arrivalStatus(view({execution_mode:'research', revision:{contact_policy:{mode:'due_reminder'}}, schedules:[]})).detail, /日程.*核对/)
  assert.match(arrivalStatus(view({execution_mode:'research', requires_comparison_baseline:true, revision:{contact_policy:{mode:'condition'}}})).title, /第一份研究/)
})

test('定时任务在执行或排队时展示当前任务，不提前宣称已完成或等待下一次', () => {
 for (const status of ['running','queued']) {
  const state=arrivalStatus(view({execution_mode:'research', revision:{contact_policy:{mode:'scheduled_delivery'}},executions:[{status}]}))
  assert.match(state.title,status==='running'?/正在按约处理/:/已排队/)
  assert.doesNotMatch(state.title,/第一份研究|已完成/)
 }
})
