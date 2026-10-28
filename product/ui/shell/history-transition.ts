// A transient presentation hint; DSH remains the owner of conversation state.
let target: string | undefined
let completed: string | undefined
export function beginHistoryTransition(id: string) {
  target = id
  completed = undefined
}
export function alreadyTransitioned(id?: string) {
  return Boolean(id && completed === id)
}
export function isHistoryTransition(id?: string) {
  return Boolean(id && target === id)
}
export function finishHistoryTransition(id?: string) {
  if (id && target === id) {
    target = undefined
    completed = id
  }
}
