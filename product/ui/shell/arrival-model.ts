import type { MandateView } from '../mandates/model.js'
import { sourceReason } from '../mandates/model.js'
export function canRetryBaseline(item: MandateView) {
  return (
    item.requires_comparison_baseline !== false &&
    !item.baseline &&
    item.mandate.status === 'tracking' &&
    item.executions.some((e) => ['failed', 'interrupted'].includes(e.status)) &&
    !item.executions.some((e) => ['running', 'queued'].includes(e.status))
  )
}
export function arrivalStatus(item: MandateView) {
  if (item.mandate.status === 'pending_requirements')
    return {
      priority: 0,
      title: '这项委托还需要补充范围',
      detail: '查看已保存的约定，核对缺少的信息。',
      action: '查看待补充内容',
    }
  if (item.position_risk) {
    const p = item.position_risk
    return {
      priority: p.reason === 'position_target_consumed' ? 1 : 4,
      title:
        p.reason === 'position_target_consumed'
          ? '持仓风险目标已触发'
          : p.reason
            ? '持仓风险计划需要核对'
            : '按已确认价格条件跟进',
      detail:
        p.reason === 'position_target_consumed'
          ? '本代次不再重复触发；实际投递请回查联系记录，需要再次跟进时明确重新布防。'
          : p.reason
            ? '请查看计划状态、成本与有效期；当前不会取得新的发送资格。'
            : `激活成本 ${p.basis_cost} 元，目标 ${p.resolved_price} 元。程序比较价格，不额外调用研究模型。`,
      action: '查看风险计划与联系记录',
    }
  }
  if (item.executions[0]?.status === 'failed')
    return {
      priority: 1,
      title: '这次研究没有完成',
      detail:
        (item.executions[0].result?.error || '本次执行没有完成，请展开研究记录核对原因。') +
        (item.executions.some((e) => e.status === 'succeeded')
          ? ' 之前成功的结果与证据仍保留。'
          : ' 已有记录与证据仍保留。'),
      action: '查看研究情况',
    }
  if (item.source_check && item.source_check.status !== 'ok')
    return {
      priority: 2,
      title: '资料核对遇到了问题',
      detail: sourceReason(item.source_check.detail),
      action: '查看资料缺口',
    }
  if (item.execution_mode === 'program_price') {
    const condition = item.decisions?.[0]?.condition_result
    return {
      priority: condition === 'met' ? 1 : 4,
      title:
        condition === 'unmet'
          ? '尚未到价，继续按约检查'
          : condition === 'met'
            ? '价格条件已满足'
            : '价格条件等待核对',
      detail:
        condition === 'unmet'
          ? '最近一次有效报价未满足价格条件；后续由程序继续比较，不需要建立研究基准。'
          : condition === 'met'
            ? '程序已按来源报价核对条件，提醒是否送达请查看联系记录。'
            : '有效报价到达后由程序核对条件；资料缺失或过期时保持未知，不视为未到价。',
      action: '查看价格依据与联系记录',
    }
  }
  if (item.decisions?.[0]?.condition_result === 'unknown')
    return {
      priority: 3,
      title: '资料已整理，结论还需等待',
      detail: '目前证据不足以判断变化；不需要你立即操作。',
      action: '查看依据与缺口',
    }
  if (!item.baseline)
    return {
      priority: 4,
      title: '正在等待第一份研究结果',
      detail: '还没有可用研究基准，你暂时不用操作。',
      action: '查看进展',
    }
  if (!item.monitoring?.enabled)
    return {
      priority: 5,
      title: '研究记录已保留',
      detail: '当前范围尚未接入持续资料发现；不会自动发现新的材料。',
      action: '查看已有研究',
    }
  return {
    priority: 5,
    title: '已有研究基准，继续按约跟进',
    detail: '可以查看已留存的研究与联系约定。',
    action: '查看研究记录',
  }
}
export function arrivalItem(items: MandateView[]) {
  return items
    .filter((x) => !['paused', 'ended'].includes(x.mandate.status))
    .map((item, index) => ({ item, index, state: arrivalStatus(item) }))
    .sort((a, b) => a.state.priority - b.state.priority || a.index - b.index)[0]
}
