import type { ChatList, ChatSummary } from '../history.js'
import type { ChildRecord, ConversationStatus } from './conversation-types.js'
export const conversationStates = {
  running: '正在处理',
  waiting_user: '等你确认',
  idle: '当前未运行',
  turn_completed: '本轮已完成',
  turn_stopped: '本轮未正常完成',
  external: '外部任务，状态待核对',
  unknown: '状态待核对',
}
export type ConversationState = keyof typeof conversationStates
export type ConversationRow = {
  id: string
  rootId: string
  rootLabel: string
  label: string
  kind: 'conversation' | 'child'
  state: ConversationState
  updatedAt?: number
}
const priority: Record<ConversationState, number> = {
  waiting_user: 0,
  running: 1,
  unknown: 2,
  external: 2,
  turn_stopped: 3,
  idle: 4,
  turn_completed: 4,
}
function needsUser(status?: ConversationStatus) {
  const pending = status?.pendingInteraction
  return (
    !!pending &&
    typeof pending === 'object' &&
    'kind' in pending &&
    ['question', 'approval', 'plan-review'].includes(String(pending.kind))
  )
}
/** DSH owns lineage and activity. Never infer completion from a stopped/absent Agent. */
export function conversationProgress(
  list: ChatList,
  statuses: ReadonlyMap<string, ConversationStatus>,
  options: {
    connected: boolean
    archiveReady: boolean
    archived: readonly string[]
  },
) {
  const rows: ConversationRow[] = [],
    refreshIds: string[] = []
  const ready = list.phase === 'ready' && options.archiveReady
  if (!ready) return { rows, refreshIds, ready, complete: false }
  const excluded = new Set(options.archived)
  const roots = list.ids
    .map((id) => list.byId[id])
    .filter(
      (s): s is ChatSummary =>
        !!s &&
        s.projectionValues?.agentPreset === 'huohuo' &&
        s.origin !== 'subagent' &&
        !excluded.has(s.id) &&
        (!s.blank ||
          (statuses.get(s.id)?.running ?? s.running) === true ||
          needsUser(statuses.get(s.id))),
    )
    .sort(
      (a, b) =>
        Number(needsUser(statuses.get(b.id))) - Number(needsUser(statuses.get(a.id))) ||
        Number((statuses.get(b.id)?.running ?? b.running) === true) -
          Number((statuses.get(a.id)?.running ?? a.running) === true) ||
        b.updatedAt - a.updatedAt,
    )
  let complete = options.connected && roots.length <= 20
  const visited = new Set<string>(),
    rootIds = new Set(roots.map((r) => r.id))
  function state(id: string, child?: ChildRecord): ConversationState {
    if (!options.connected) return 'unknown'
    if (child?.mode === 'external') return 'external'
    const current = statuses.get(id),
      summary = list.byId[id]
    if (needsUser(current)) return 'waiting_user'
    const running = current?.running ?? summary?.running
    if (running === true) return 'running'
    if (running !== false) return 'unknown'
    if (child && child.mode !== 'unknown') {
      const projection = list.projectionsBySession?.[id]
      const completed =
        projection?.state === 'ready'
          ? projection.values.subagentTiming?.lastTurnCompleted
          : undefined
      if (completed === true) return 'turn_completed'
      if (completed === false) return 'turn_stopped'
    }
    return 'idle'
  }
  function children(parent: string, root: ChatSummary, depth: number) {
    if (depth > 16) {
      complete = false
      return
    }
    refreshIds.push(parent)
    const projection = list.projectionsBySession?.[parent]
    if (!projection || projection.state !== 'ready' || !projection.values.subagentCatalog)
      complete = false
    for (const child of projection?.values.subagentCatalog ?? []) {
      if (visited.has(child.id) || rootIds.has(child.id)) {
        complete = false
        continue
      }
      visited.add(child.id)
      const childState = state(child.id, child)
      if (childState === 'unknown' || childState === 'external') complete = false
      rows.push({
        id: child.id,
        rootId: root.id,
        rootLabel: root.title?.trim() || '未命名对话',
        label: child.label?.trim() || list.byId[child.id]?.title?.trim() || '未命名子任务',
        kind: 'child',
        state: childState,
        updatedAt: list.byId[child.id]?.updatedAt ?? child.createdAt,
      })
      if (child.mode !== 'external') children(child.id, root, depth + 1)
    }
  }
  for (const root of roots.slice(0, 20)) {
    visited.add(root.id)
    const label = root.title?.trim() || '未命名对话'
    rows.push({
      id: root.id,
      rootId: root.id,
      rootLabel: label,
      label,
      kind: 'conversation',
      state: state(root.id),
      updatedAt: root.updatedAt,
    })
    children(root.id, root, 0)
  }
  rows.sort(
    (a, b) => priority[a.state] - priority[b.state] || (b.updatedAt ?? 0) - (a.updatedAt ?? 0),
  )
  return { rows, refreshIds: [...new Set(refreshIds)], ready, complete }
}
