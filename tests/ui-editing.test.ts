import test from 'node:test'
import assert from 'node:assert/strict'
import {
  notificationDraft,
  notificationPatch,
  notificationIssue,
} from '../product/ui/notifications/editor-model.js'
import { initialDraft, previewCommand } from '../product/ui/investment/editor-model.js'
import { selectableSecurities, searchMessage } from '../product/ui/investment/search-model.js'
import { arrivalItem, arrivalStatus } from '../product/ui/shell/arrival-model.js'
import type { Config } from '../product/ui/notifications/model.js'
import type { MandateView } from '../product/ui/mandates/model.js'
import { quantityUnit } from '../product/ui/investment/types.js'
test('股票和场内基金单位贯穿新建表单及服务端投影', () => {
  assert.equal(quantityUnit({ code: '513130' }), '份')
  assert.equal(quantityUnit({ code: '159740' }), '份')
  assert.equal(quantityUnit({ ticker: '600519' }), '股')
  assert.equal(quantityUnit({ ticker: '600519', quantity_unit: '份' }), '份')
})
const config: Config = {
  revision: 7,
  enabled: true,
  channels: ['app', 'email'],
  timezone: 'Asia/Shanghai',
  quiet_hours: { start: '22:00', end: '08:00' },
  external_status: '',
  external: {
    email: {
      configured: true,
      secret_saved: { password: true },
      host: 'mail.example.test',
      port: 587,
    },
  },
}
test('渠道编辑只提交当前渠道；静默编辑不携带渠道凭据', () => {
  const d = notificationDraft(config, 'email')
  d.external.password = 'fixture-only'
  d.start = '00:00'
  const patch = notificationPatch(config, 'email', d)
  assert.deepEqual(Object.keys(patch.external), ['email'])
  assert.deepEqual(patch.quiet_hours, config.quiet_hours)
  assert.equal(patch.expected_revision, 7)
  const schedule = notificationPatch(config, 'schedule', { ...d, start: '21:00' })
  assert.deepEqual(schedule.external, {})
  assert.equal(schedule.quiet_hours?.start, '21:00')
  assert.deepEqual(schedule.channels, config.channels)
  assert.equal(notificationDraft(config, 'email').external.password, '')
})
test('清除渠道配置同时撤销该渠道启用，保留其他渠道', () => {
  const draft = notificationDraft(config, 'email')
  draft.external = { clear: true }
  const patch = notificationPatch(config, 'email', draft)
  assert.deepEqual(patch.channels, ['app'])
  assert.deepEqual(patch.external, { email: { clear: true } })
})
test('证券搜索过期及失败均不可供选择，失败不伪装未找到', () => {
  const candidates = [{ code: '600519', name: '合成证券' }]
  for (const status of ['stale', 'unavailable', 'empty'] as const) {
    const result = { status, usable_for_confirmation: false, candidates }
    assert.deepEqual(selectableSecurities(result), [])
    assert.ok(searchMessage(result))
  }
  assert.deepEqual(
    selectableSecurities({ status: 'ok', usable_for_confirmation: true, candidates }),
    candidates,
  )
})
test('证券未选择不能预览；修改词导致清除选择后旧证券不能提交', () => {
  const target = { kind: 'holding' as const }
  const draft = initialDraft(target)
  assert.throws(() => previewCommand(target, draft, 'test'), /选择证券/)
  draft.security = { code: '600519', name: '合成证券' }
  draft.quantity = '100'
  draft.price = ''
  assert.deepEqual(
    (previewCommand(target, draft, 'test').payload as { cost_price: number | null }).cost_price,
    null,
  )
  draft.security = undefined
  assert.throws(() => previewCommand(target, draft, 'test'), /选择证券/)
})
test('未知判断不生成待决定；正常跟进不会掩盖失败', () => {
  const base = {
    mandate: { mandate_id: 'a', status: 'tracking' },
    baseline: { summary: '基准' },
    executions: [],
    decisions: [{ condition_result: 'unknown' }],
  } as unknown as MandateView
  assert.match(arrivalStatus(base).detail, /不需要你立即操作/)
  const failed = {
    ...base,
    mandate: { ...base.mandate, mandate_id: 'b' },
    executions: [{ execution_id: 'e', status: 'failed' }] as MandateView['executions'],
  }
  assert.equal(arrivalItem([base, failed])?.item.mandate.mandate_id, 'b')
  assert.equal(arrivalItem([{ ...base, mandate: { ...base.mandate, status: 'ended' } }]), undefined)
})

test('最后一个渠道不能关闭，未接入持续发现不承诺自动跟进', () => {
  const only = { ...config, channels: ['app'] }
  const draft = notificationDraft(only, 'app')
  draft.channelEnabled = false
  assert.match(notificationIssue(only, 'app', draft), /总开关/)
  const view = {
    mandate: { status: 'tracking' },
    baseline: { summary: '基准' },
    executions: [],
    monitoring: { enabled: false, detail: '未接入' },
  } as unknown as MandateView
  assert.match(arrivalStatus(view).detail, /不会自动发现/)
})

test('行内成交入口不把持仓数量和成本冒充成交值', () => {
  const position = {
    ticker: '000001',
    name: '合成证券',
    quantity: 200,
    cost_price: 12,
  } as import('../product/ui/investment/types.js').Position
  const draft = initialDraft({ kind: 'trade', position })
  assert.equal(draft.security?.name, '合成证券')
  assert.equal(draft.quantity, '')
  assert.equal(draft.price, '')
  const correction = initialDraft({ kind: 'holding', position })
  assert.equal(correction.quantity, '200')
  assert.equal(correction.price, '12')
})

test('成交使用已选名称，已有只读展示名称可进入编辑器', () => {
  const target = { kind: 'trade' as const }
  const draft = {
    ...initialDraft(target),
    security: { code: '000001', name: '合成银行' },
    quantity: '200',
    price: '11.18',
    fees: '5',
  }
  const command = previewCommand(target, draft, 'name-trade')
  assert.equal((command.payload as any).name, '合成银行')
  assert.equal(
    initialDraft({
      kind: 'holding',
      position: { ticker: '000001', quantity: 200, cost_price: 11.205, display_name: '目录银行' },
    }).security?.name,
    '目录银行',
  )
})
