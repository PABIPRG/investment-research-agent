// A transient presentation hint; DSH remains the owner of conversation state.
export interface CompanionOrigin {
  left: number
  top: number
  width: number
  height: number
  kind: 'welcome' | 'response' | 'question'
}
export function historyMotion(
  from: CompanionOrigin['kind'],
  to: CompanionOrigin['kind'],
  reduced: boolean,
) {
  // The question card is another landing point, not a cue to spin the model.
  const turn = !reduced && from !== to && (from === 'welcome' || to === 'welcome')
  return { turn, duration: reduced ? 0 : turn ? 560 : 420 }
}
interface HistoryTransition {
  id: string
  revision: number
  expiresAt: number
  origin?: CompanionOrigin
}
let target: HistoryTransition | undefined
let completed: string | undefined
let revision = 0
export function beginHistoryTransition(id: string, origin?: CompanionOrigin) {
  target = {
    id,
    revision: ++revision,
    expiresAt: Date.now() + 8000,
    origin: origin && { ...origin },
  }
  completed = undefined
}
export function historyTransition(id?: string) {
  if (target && target.expiresAt <= Date.now()) target = undefined
  return target?.id === id ? target : undefined
}
export function updateHistoryOrigin(
  id: string | undefined,
  version: number,
  origin: CompanionOrigin,
) {
  if (!target || target.id !== id || target.revision !== version) return false
  target.origin = { ...origin }
  return true
}
export function alreadyTransitioned(id?: string) {
  return Boolean(id && completed === id)
}
export function isHistoryTransition(id?: string) {
  return Boolean(id && historyTransition(id))
}
export function finishHistoryTransition(id?: string, version?: number) {
  if (id && target?.id === id && (version === undefined || target.revision === version)) {
    target = undefined
    completed = id
  }
}

export function captureCompanionOrigin(root: HTMLElement | null): CompanionOrigin | undefined {
  const dock = root?.querySelector<HTMLElement>('[data-huohuo-companion]')
  if (!dock || getComputedStyle(dock).visibility === 'hidden') return
  // Capture the currently visible model bounds when a new selection interrupts movement.
  const rect = (
    dock.querySelector<HTMLElement>('[data-companion-model]') ?? dock
  ).getBoundingClientRect()
  if (!rect.width || !rect.height) return
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    kind:
      root?.dataset.arrival === 'true'
        ? 'welcome'
        : root?.dataset.companionTarget === 'question'
          ? 'question'
          : 'response',
  }
}
