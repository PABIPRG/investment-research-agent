import { useSyncExternalStore } from 'react'
import type { CompanionMotion } from '../companion-state.js'
const listeners = new Set<() => void>()
let snapshot = { motion: 'idle' as CompanionMotion, arrival: false, visible: false }
export function presentCompanion(next: typeof snapshot) {
  if (JSON.stringify(next) === JSON.stringify(snapshot)) return
  snapshot = next
  for (const fn of listeners) fn()
}
export function useCompanionPresentation() {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn)
      return () => {
        listeners.delete(fn)
      }
    },
    () => snapshot,
  )
}
