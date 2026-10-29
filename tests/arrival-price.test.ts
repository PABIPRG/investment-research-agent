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
