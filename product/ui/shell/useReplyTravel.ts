import { useCallback, useLayoutEffect, useRef, type RefObject } from 'react'
import { ReplyTurnTracker } from './reply-travel.js'

/** Keep normal replies continuous without animating every scroll or streaming chunk. */
export function useReplyTravel(root: RefObject<HTMLDivElement>, sessionId?: string) {
  const tracker = useRef(new ReplyTurnTracker())
  const timer = useRef(0)
  const start = useCallback(() => {
    const el = root.current
    if (!el || el.dataset.companionPositioned !== 'true') return
    el.dataset.replyTravel = 'true'
    clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      delete el.dataset.replyTravel
    }, 520)
  }, [root])
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const cancel = () => {
      clearTimeout(timer.current)
      delete el.dataset.replyTravel
    }
    const key = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      // Prepare only the visual transition before DSH scrolls; never submit/intercept input.
      if (
        event.key === 'Enter' &&
        !event.shiftKey &&
        !event.isComposing &&
        target?.closest('[data-composer-seat]') &&
        el.dataset.arrival === 'false'
      )
        start()
      if (['PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
        if (!target?.closest('textarea,input,[contenteditable="true"]')) cancel()
      }
    }
    const click = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (
        el.dataset.arrival === 'false' &&
        target?.closest(
          '[data-composer-seat] button[aria-label="发送消息"], [data-composer-seat] button[aria-label="Send message"]',
        )
      )
        start()
    }
    el.addEventListener('wheel', cancel, { passive: true })
    el.addEventListener('touchstart', cancel, { passive: true })
    el.addEventListener('keydown', key, true)
    el.addEventListener('click', click, true)
    return () => {
      cancel()
      el.removeEventListener('wheel', cancel)
      el.removeEventListener('touchstart', cancel)
      el.removeEventListener('keydown', key, true)
      el.removeEventListener('click', click, true)
    }
  }, [root, sessionId, start])
  return useCallback(
    (turn: number | undefined, enabled: boolean) => {
      const changed = tracker.current.visit(sessionId, turn)
      const el = root.current
      if (!el) return
      if (!enabled) {
        clearTimeout(timer.current)
        delete el.dataset.replyTravel
        return
      }
      if (changed) start()
    },
    [root, sessionId, start],
  )
}
