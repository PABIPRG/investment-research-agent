export interface ChatSummary {
  id: string
  title?: string
  parentId?: string
  origin?: 'subagent'
  running: boolean
  blank: boolean
  updatedAt: number
  retainedBy?: { mainView?: number }
  projectionValues?: { agentPreset?: string | null }
}
export interface ChatList {
  ids: string[]
  byId: Record<string, ChatSummary>
  phase: 'pending' | 'ready'
}
/** Navigation is a projection of DSH-owned data, never a second conversation store. */
export function historyRows(
  list: ChatList,
  archived: readonly string[],
  selected?: string,
  archiveReady = true,
) {
  if (list.phase !== 'ready' || !archiveReady) return []
  const excluded = new Set(archived)
  return list.ids
    .map((id) => list.byId[id])
    .filter(
      (row): row is ChatSummary =>
        !!row &&
        row.projectionValues?.agentPreset === 'huohuo' &&
        row.origin !== 'subagent' &&
        !excluded.has(row.id) &&
        (!row.blank || row.id === selected),
    )
    .sort((a, b) => b.updatedAt - a.updatedAt || a.id.localeCompare(b.id))
    .map((row) => ({ ...row, label: row.title?.trim() || (row.blank ? '新对话' : '未命名对话') }))
}
