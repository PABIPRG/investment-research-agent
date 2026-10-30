import type { MandateView } from '../mandates/model.js'
import { mandateName } from '../business-model.js'
import { decisionText } from '../notifications/model.js'
import type { ActivityRecord } from './model.js'
import type { ConversationRow } from './conversation-model.js'

export type Change = {
  id: string
  kind: 'research' | 'reminder'
  name: string
  source: string
  title: string
  summary: string
  at?: number
  mandateId: string
  decisionId: string
  executionId?: string
  records: ActivityRecord[]
  evidenceCount?: number
  warning?: string
}
export type Attention = {
  id: string
  title: string
  detail: string
  action: string
  mandateId: string
  source: string
}
function savedTime(value?: number) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}
/** Read-only projection: never create a finding from a configuration or a running task. */
export function dashboardEvents(
  mandates: readonly MandateView[],
  records: readonly ActivityRecord[],
) {
  const events: Change[] = []
  for (const item of mandates) {
    const name = mandateName(item)
    for (const execution of item.executions) {
      const succeeded = execution.status === 'succeeded' && !!execution.result?.summary
      const failed = ['failed', 'interrupted'].includes(execution.status)
      if (!succeeded && !failed) continue
      events.push({
        id: `execution:${execution.execution_id}`,
        kind: 'research',
        name,
        source: item.revision.goal,
        title: `${name}：${succeeded ? '研究结果已保存' : execution.status === 'interrupted' ? '本次研究已中断' : '本次研究未完成'}`,
        summary:
          execution.result?.summary ||
          execution.result?.error ||
          '请回到委托查看执行原因与已有记录。',
        at: savedTime(execution.updated_at),
        mandateId: item.mandate.mandate_id,
        decisionId: '',
        executionId: execution.execution_id,
        records: [],
        evidenceCount: execution.result?.evidence_ids?.length,
        warning: failed
          ? '结果尚未完成'
          : Object.values(execution.result?.judgements ?? {}).some((j) =>
                ['unknown', 'error'].includes(j.judgement),
              )
            ? '部分判断待核实'
            : undefined,
      })
    }
  }
  const grouped = new Map<string, ActivityRecord[]>()
  for (const row of records) {
    const key = JSON.stringify([row.mandate_id, row.decision_id])
    grouped.set(key, [...(grouped.get(key) ?? []), row])
  }
  for (const rows of grouped.values()) {
    const row = rows[0]
    const item = mandates.find((m) => m.mandate.mandate_id === row.mandate_id)
    const name = item ? mandateName(item) : '相关委托暂未读取'
    const times = rows
      .map((r) => savedTime(r.updated_at ?? r.created_at))
      .filter((n): n is number => n !== undefined)
    events.push({
      id: `decision:${row.mandate_id}:${row.decision_id}`,
      kind: 'reminder',
      name,
      source: item?.revision.goal || name,
      title: `${name}：${row.reason_code === 'due_reminder' ? '按约到期提醒' : '已保存提醒记录'}`,
      summary: decisionText(row.decision_detail || '', row.reason_code || ''),
      at: times.length ? Math.max(...times) : undefined,
      mandateId: row.mandate_id,
      decisionId: row.decision_id,
      records: rows,
    })
  }
  return events.sort((a, b) => (b.at ?? 0) - (a.at ?? 0) || a.id.localeCompare(b.id))
}
export function splitChanges(events: readonly Change[], now: number) {
  const isRecent = (e: Change) => e.at !== undefined && e.at <= now && e.at >= now - 48 * 3600
  return { recent: events.filter(isRecent), history: events.filter((e) => !isRecent(e)) }
}
export function splitConversations(rows: readonly ConversationRow[]) {
  return {
    attention: rows.filter((r) => r.state === 'waiting_user'),
    running: rows.filter((r) => r.state === 'running'),
    uncertain: rows.filter((r) => ['unknown', 'external', 'turn_stopped'].includes(r.state)),
    history: rows.filter((r) => ['idle', 'turn_completed'].includes(r.state)),
  }
}
export function mandateAttention(items: readonly MandateView[]): Attention[] {
  return [...items]
    .sort(
      (a, b) =>
        Number(b.mandate.status === 'pending_requirements') -
        Number(a.mandate.status === 'pending_requirements'),
    )
    .flatMap((item) => {
      if (!['tracking', 'pending_requirements'].includes(item.mandate.status)) return []
      const pending = item.mandate.status === 'pending_requirements'
      const execution = item.executions[0]
      if (!pending && !['failed', 'interrupted'].includes(execution?.status ?? '')) return []
      return [
        {
          id: `mandate:${item.mandate.mandate_id}`,
          title: `${mandateName(item)}：${pending ? '请补充研究范围' : '请核对上次研究未完成的原因'}`,
          detail: pending
            ? '当前约定尚未完整，请回到委托补充后再继续。'
            : '已有执行记录保留在委托详情中；不会在此自动重试。',
          action: pending ? '补充委托信息' : '查看原因',
          mandateId: item.mandate.mandate_id,
          source: item.revision.goal,
        },
      ]
    })
}
