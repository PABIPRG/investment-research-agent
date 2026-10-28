export interface ActivityRecord {
  decision_id: string
  mandate_id: string
  channel: string
  status: string
  detail?: string
  decision_detail?: string
  reason_code?: string
  created_at?: number
  updated_at?: number
}
export type SeenActivity = Record<string, string>
/** Count saved decisions once, even if delivered through several channels. */
export function activityVersions(items: readonly ActivityRecord[]): SeenActivity {
  const grouped = new Map<string, string[]>()
  for (const row of items) {
    if (!row.decision_id) continue
    const versions = grouped.get(row.decision_id) ?? []
    versions.push(
      JSON.stringify([row.channel, row.status, row.detail, row.decision_detail, row.updated_at]),
    )
    grouped.set(row.decision_id, versions)
  }
  return Object.fromEntries(
    [...grouped].map(([id, versions]) => [id, JSON.stringify(versions.sort())]),
  )
}
export function unseenActivity(items: readonly ActivityRecord[], seen: SeenActivity): number {
  return Object.entries(activityVersions(items)).filter(([id, version]) => seen[id] !== version)
    .length
}
export function rememberActivity(
  seen: SeenActivity,
  visible: readonly ActivityRecord[],
): SeenActivity {
  return Object.fromEntries(Object.entries({ ...seen, ...activityVersions(visible) }).slice(-1000))
}
