/** Animation reflects observed UI state, never a fabricated research result. */
export type CompanionMotion =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'working'
  | 'speaking'
  | 'awaiting_reply'
  | 'gentle_knock'
  | 'sigh'
export function companionMotion(input: {
  failed?: boolean
  pending?: boolean
  running?: boolean
  streaming?: boolean
  working?: boolean
  draft?: string
}): CompanionMotion {
  if (input.pending) return 'awaiting_reply'
  if (input.running && input.working) return 'working'
  if (input.streaming) return 'speaking'
  if (input.running) return 'thinking'
  if (input.draft?.trim()) return 'listening'
  if (input.failed) return 'sigh'
  return 'idle'
}
