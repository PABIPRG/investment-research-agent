import type { Change } from './dashboard-model.js'
export type ChangeGroup = {
  id: string
  latest: Change
  rows: Change[]
  incomplete: number
  uncertain: number
}
/** Group only saved research executions for the same mandate and known revision. */
export function groupChanges(rows: readonly Change[]): ChangeGroup[] {
  const groups = new Map<string, ChangeGroup>()
  for (const row of rows) {
    const id =
      row.kind === 'research' && Number.isInteger(row.revision) && (row.revision ?? 0) > 0
        ? JSON.stringify(['research', row.mandateId, row.revision])
        : JSON.stringify([row.kind, row.id])
    let group = groups.get(id)
    if (!group) {
      group = { id, latest: row, rows: [], incomplete: 0, uncertain: 0 }
      groups.set(id, group)
    }
    group.rows.push(row)
    if (row.outcome === 'failed' || row.outcome === 'interrupted') group.incomplete++
    if (row.outcome === 'succeeded' && row.warning) group.uncertain++
  }
  return [...groups.values()]
}
export function visibleChanges(groups: readonly ChangeGroup[], limit: number) {
  return groups.slice(0, limit)
}
