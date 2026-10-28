// Transient visual coordinates; conversation state continues to belong to DSH.
let origin: { x: number; y: number; width: number; height: number } | undefined
export function beginWelcomeTransition(rect: DOMRect) {
  origin = { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
}
export function welcomeTransition() {
  return origin
}
export function finishWelcomeTransition() {
  origin = undefined
}
