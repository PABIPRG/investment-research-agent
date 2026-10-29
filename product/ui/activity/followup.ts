import type { MandateView } from '../mandates/model.js'
import { sourceReason } from '../mandates/model.js'
import { nextTrigger } from '../mandates/triggers.js'
type Kind = 'running' | 'queued' | 'attention' | 'waiting' | 'unavailable'
export const progressLabels: Record<Kind, string> = {
  running: '研究中',
  queued: '等待开始',
  attention: '需要留意',
  waiting: '等待下次跟进',
  unavailable: '跟进安排待核对',
}
const order: Record<Kind, number> = {
  running: 0,
  queued: 1,
  attention: 2,
  waiting: 3,
  unavailable: 4,
}
function progress(item: MandateView): { kind: Kind; detail: string; updatedAt?: number } {
  const execution = item.executions[0]
  if (execution?.status === 'running')
    return {
      kind: 'running',
      detail: '后台已领取这项研究，结果尚未保存。',
      updatedAt: execution.updated_at,
    }
  if (execution?.status === 'queued')
    return {
      kind: 'queued',
      detail: '研究请求已保存，等待后台领取；排队不代表已经开始。',
      updatedAt: execution.updated_at,
    }
  if (item.mandate.status === 'pending_requirements')
    return {
      kind: 'attention',
      detail: '研究范围还需补充，请到委托详情核对。',
    }
  if (execution && ['failed', 'interrupted'].includes(execution.status))
    return {
      kind: 'attention',
      detail: '上次研究未完成，请到委托详情查看原因与已有记录。',
      updatedAt: execution.updated_at,
    }
  if (item.source_check && item.source_check.status !== 'ok')
    return {
      kind: 'attention',
      detail: sourceReason(item.source_check.detail),
    }
  const mode = item.revision.contact_policy?.mode
  if (mode && mode !== 'condition') {
    const scheduled = item.schedules?.some(
      (s) => s.enabled !== false && Number.isFinite(Date.parse(s.next_due_at)),
    )
    return { kind: scheduled ? 'waiting' : 'unavailable', detail: nextTrigger(item) }
  }
  return item.monitoring.enabled
    ? { kind: 'waiting', detail: item.monitoring.detail }
    : {
        kind: 'unavailable',
        detail: item.monitoring.detail || '暂不能确认下一次跟进安排，请查看委托详情。',
      }
}
/** Configuration describes a plan; only saved execution state describes an active research task. */
export function followupProgress(items: readonly MandateView[]) {
  return items
    .filter((item) => ['tracking', 'pending_requirements'].includes(item.mandate.status))
    .map((item) => ({ item, ...progress(item) }))
    .sort((a, b) => order[a.kind] - order[b.kind])
}
