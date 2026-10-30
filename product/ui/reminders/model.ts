export interface Reminder {
  id: string
  kind: 'test' | 'mandate'
  title: string
  body: string
  created_at: number
  mandate_id?: string
  decision_id?: string
}
export interface Feed {
  scope: string
  items: Reminder[]
}
export interface ReminderState {
  scope: string
  seen: string[]
  pending: Reminder[]
}
export function ingest(
  state: ReminderState,
  feed: Feed,
  bootstrap = false,
  restored: string[] = [],
): ReminderState {
  const same = state.scope === feed.scope
  const seen = new Set(same ? state.seen : [])
  const pending = same ? [...state.pending] : []
  for (const row of feed.items) {
    if (!row.id || !['test', 'mandate'].includes(row.kind) || !Number.isFinite(row.created_at))
      continue
    if (!seen.has(row.id) && (!bootstrap || restored.includes(row.id))) pending.push(row)
    seen.add(row.id)
  }
  return { scope: feed.scope, seen: [...seen].slice(-1000), pending }
}
export function acknowledge(state: ReminderState, id: string): ReminderState {
  return { ...state, pending: state.pending.filter((row) => row.id !== id) }
}
