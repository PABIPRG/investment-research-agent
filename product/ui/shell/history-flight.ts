import {
  captureCompanionOrigin,
  finishHistoryTransition,
  historyTransition,
  historyMotion,
  updateHistoryOrigin,
  type CompanionOrigin,
} from './history-transition.js'

/** A cancellable presentation bridge across native Session remounts. No conversation state. */
export function historyFlight(root: HTMLElement, id?: string, fallback?: CompanionOrigin) {
  const ticket = historyTransition(id)
  const source = ticket?.origin ?? fallback
  const body = root.querySelector<HTMLElement>('[data-huohuo-chat-body]')
  let waiting = Boolean(ticket && source && body)
  let moving = false
  let frame = 0
  let timer = 0
  let deadline = 0
  let destination: CompanionOrigin['kind'] | undefined
  const valid = () => Boolean(ticket && historyTransition(id)?.revision === ticket.revision)
  const clear = () => {
    if (!ticket || root.dataset.historyRevision !== String(ticket.revision)) return
    delete root.dataset.historyTransition
    delete root.dataset.historyTurn
    delete root.dataset.historyRevision
  }
  const finish = () => {
    if (valid()) finishHistoryTransition(id, ticket!.revision)
    waiting = moving = false
    clear()
  }
  if (waiting && source && body) {
    const rect = body.getBoundingClientRect()
    for (const [key, value] of Object.entries({
      left: source.left - rect.left,
      top: source.top - rect.top,
      width: source.width,
      height: source.height,
    }))
      body.style.setProperty(`--hh-departure-${key}`, `${value}px`)
    root.dataset.historyTransition = 'waiting'
    root.dataset.historyRevision = String(ticket!.revision)
    deadline = window.setTimeout(finish, Math.max(0, ticket!.expiresAt - Date.now()))
  } else if (ticket) finish()
  return {
    get waiting() {
      return waiting
    },
    get active() {
      return waiting || moving
    },
    finish,
    move(kind: CompanionOrigin['kind'], model?: string) {
      if (!waiting || frame || (model !== 'ready' && model !== 'failed')) return
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => {
          if (!valid()) return
          waiting = false
          moving = true
          destination = kind
          clearTimeout(deadline)
          const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
          const { turn, duration } = historyMotion(source!.kind, kind, reduced)
          body?.style.setProperty('--hh-history-duration', `${duration}ms`)
          root.dataset.historyTurn = String(turn)
          root.dataset.historyTransition = 'moving'
          if (turn) root.dispatchEvent(new Event('huohuo-companion-travel'))
          timer = window.setTimeout(finish, duration + 30)
        })
      })
    },
    stop() {
      cancelAnimationFrame(frame)
      clearTimeout(timer)
      clearTimeout(deadline)
      if (valid() && source) {
        const visible = captureCompanionOrigin(root)
        if (visible)
          updateHistoryOrigin(id, ticket!.revision, {
            ...visible,
            kind: waiting ? source.kind : (destination ?? visible.kind),
          })
      }
      waiting = moving = false
      clear()
    },
  }
}
