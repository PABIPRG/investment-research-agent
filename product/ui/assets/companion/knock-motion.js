/** Reuse the authored hand/contact/ripple clip, once; ordinary poses keep looping. */
export function configureAction(action, name, canvas, once, repeat) {
  const knocking = name === 'gentle_knock'
  action.setLoop(knocking ? once : repeat, knocking ? 1 : Infinity)
  action.clampWhenFinished = knocking
  if (knocking) canvas.dataset.knockCount = String(Number(canvas.dataset.knockCount || 0) + 1)
  return action
}
