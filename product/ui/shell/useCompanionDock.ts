import { useLayoutEffect, useRef, type RefObject } from 'react'
import { useCompanionOrigin } from './useCompanionOrigin.js'
import { useReplyTravel } from './useReplyTravel.js'
import { dockPoint, responseAnchor } from './dock-model.js'
import {
  alreadyTransitioned,
  beginHistoryTransition,
  finishHistoryTransition,
  isHistoryTransition,
} from './history-transition.js'
import { finishWelcomeTransition, welcomeTransition } from './welcome-transition.js'
import { historyFlight } from './history-flight.js'
interface DockState {
  sessionId?: string
  blank: boolean
  pending: boolean
  quiet: boolean
  view: 'chat' | 'trajectory'
  openState?: string
}
/** Geometry follows one native Turn origin, not whichever fragment rendered last. */
export function useCompanionDock(root: RefObject<HTMLDivElement>, state: DockState) {
  const previous = useRef<{ sessionId?: string; stage: string }>()
  const departure = useCompanionOrigin(root)
  const followReply = useReplyTravel(root, state.sessionId)
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const { sessionId, blank, pending, quiet, view, openState } = state
    const leavingWelcome = previous.current?.stage === 'welcome' && !blank
    if (
      leavingWelcome &&
      sessionId &&
      !isHistoryTransition(sessionId) &&
      !alreadyTransitioned(sessionId)
    )
      beginHistoryTransition(sessionId)
    if (isHistoryTransition(sessionId) && (quiet || view !== 'chat'))
      finishHistoryTransition(sessionId)
    const history = historyFlight(el, sessionId, departure.current)
    let welcomeFrame = 0
    let welcomeTimer = 0
    let returning = Boolean(blank && welcomeTransition() && !quiet && view === 'chat')
    if (returning) el.dataset.welcomeTransition = 'waiting'
    if (!blank && previous.current?.stage === 'welcome') finishWelcomeTransition()
    if (blank && (quiet || view !== 'chat')) finishWelcomeTransition()
    const stage = blank ? 'welcome' : pending ? 'question' : 'response'
    const travel = Boolean(
      previous.current &&
        previous.current.sessionId === sessionId &&
        previous.current.stage !== stage,
    )
    previous.current = { sessionId, stage }
    el.dataset.companionPositioned = 'false'
    el.dataset.companionTravel = String(Boolean(travel))
    // Reply/question changes only move the dock; welcome transitions handle their own turn.
    const travelTimer = setTimeout(() => {
      el.dataset.companionTravel = 'false'
    }, 520)
    let frame = 0
    const set = (body: HTMLElement, key: string, value: number) => {
      const text = `${Math.round(value * 2) / 2}px`
      if (body.style.getPropertyValue(key) !== text) body.style.setProperty(key, text)
    }
    const update = () => {
      frame = 0
      const body = el.querySelector<HTMLElement>('[data-huohuo-chat-body]')
      if (!body || quiet || view !== 'chat') return
      const bodyRect = body.getBoundingClientRect()
      const arrival = el.querySelector<HTMLElement>('[data-huohuo-arrival]')
      if (history.waiting && (blank || !openState || openState === 'loading')) {
        el.dataset.companionPositioned = 'true'
        return
      }
      if (history.waiting && openState === 'error') history.finish()
      if (blank && arrival && !history.waiting) {
        resize.observe(arrival)
        const account = body.querySelector<HTMLElement>('[aria-label="我的账户"]')
        if (account) {
          resize.observe(account)
          if (getComputedStyle(account).position === 'absolute')
            set(body, '--hh-arrival-offset', Math.max(148, account.offsetHeight + 30))
        }
        const height = parseFloat(getComputedStyle(el).getPropertyValue('--hh-arrival-height'))
        const top =
          arrival.getBoundingClientRect().top -
          bodyRect.top +
          body.scrollTop +
          (arrival.offsetHeight - height) / 2
        set(body, '--hh-arrival-top', top)
        set(body, '--hh-greet-y', body.clientHeight / 2 - top - height / 2)
        el.dataset.companionPositioned = 'true'
        if (returning && !welcomeFrame) {
          const dock = el.querySelector<HTMLElement>('[data-huohuo-companion]')
          const origin = welcomeTransition()
          if (dock && origin) {
            const width = dock.offsetWidth
            const finalLeft = body.clientWidth <= 600 ? 16 : (body.clientWidth - width) / 2
            set(
              body,
              '--hh-return-x',
              origin.x + origin.width / 2 - bodyRect.left - finalLeft - width / 2,
            )
            set(
              body,
              '--hh-return-y',
              origin.y + origin.height / 2 - bodyRect.top - top - height / 2,
            )
            body.style.setProperty('--hh-return-scale', String(origin.height / height))
            const model =
              el.querySelector<HTMLElement>('[data-companion-model]')?.dataset.companionModel
            if (model === 'ready' || model === 'failed') {
              welcomeFrame = requestAnimationFrame(() => {
                welcomeFrame = requestAnimationFrame(() => {
                  returning = false
                  finishWelcomeTransition()
                  el.dataset.welcomeTransition = 'moving'
                  el.dispatchEvent(new Event('huohuo-companion-travel'))
                  welcomeTimer = window.setTimeout(() => {
                    delete el.dataset.welcomeTransition
                  }, 620)
                })
              })
            }
          }
        }
        return
      }
      const rows = Array.from(
        el.querySelectorAll<HTMLElement>('[data-chat-flow-kind][data-chat-node-key]'),
      ).filter((node) => node.getClientRects().length > 0)
      const anchors = rows.map((node) => ({
        key: node.dataset.chatNodeKey!,
        turn: Number(node.dataset.chatTurn),
        kind: node.dataset.chatFlowKind!,
        part: node.dataset.chatGroupPart,
        visible: node.getBoundingClientRect().height > 0,
      }))
      const anchor = responseAnchor(anchors)
      const question = pending
        ? Array.from(el.querySelectorAll<HTMLElement>('[data-question-key]')).findLast(
            (node) => node.getBoundingClientRect().height > 0,
          )
        : undefined
      const target = question ?? rows.find((node) => node.dataset.chatNodeKey === anchor?.key)
      if (!target) {
        el.dataset.companionPositioned =
          history.active || el.dataset.companionTarget ? 'true' : 'false'
        return
      }
      const rect = (question?.querySelector('section') ?? target).getBoundingClientRect()
      const composer = el.querySelector<HTMLElement>('[data-composer-seat]')
      if (composer) resize.observe(composer)
      const flow = el.querySelector<HTMLElement>('[data-chat-flow]')
      if (flow) resize.observe(flow)
      const sizing = getComputedStyle(el)
      const width = parseFloat(sizing.getPropertyValue('--hh-dock-width'))
      const height = parseFloat(sizing.getPropertyValue('--hh-dock-height'))
      const point = question
        ? {
            left: Math.max(4, rect.left - bodyRect.left - width * 0.15),
            top: Math.max(8, rect.top - bodyRect.top - height * 0.7),
          }
        : dockPoint({
            x: rect.left - bodyRect.left,
            y: (anchor?.kind === 'user' && !question ? rect.bottom + 12 : rect.top) - bodyRect.top,
            bodyWidth: body.clientWidth,
            bodyHeight: body.clientHeight,
            width,
            height,
            composerTop:
              pending || !composer
                ? undefined
                : composer.getBoundingClientRect().top - bodyRect.top,
          })
      followReply(anchor?.turn, !pending && !history.active)
      set(body, '--hh-dock-left', point.left)
      set(body, '--hh-dock-top', point.top)
      el.dataset.companionTarget = question ? 'question' : anchor?.key
      el.dataset.companionPositioned = 'true'
      const model = el.querySelector<HTMLElement>('[data-companion-model]')?.dataset.companionModel
      history.move(question ? 'question' : 'response', model)
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    const observer = new MutationObserver(schedule)
    observer.observe(el, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['open', 'aria-expanded', 'data-companion-model'],
    })
    const resize = new ResizeObserver(schedule)
    resize.observe(el)
    el.addEventListener('scroll', schedule, true)
    el.addEventListener('toggle', schedule, true)
    update()
    return () => {
      cancelAnimationFrame(frame)
      cancelAnimationFrame(welcomeFrame)
      history.stop()
      clearTimeout(welcomeTimer)
      if (el.dataset.welcomeTransition === 'moving') delete el.dataset.welcomeTransition
      clearTimeout(travelTimer)
      observer.disconnect()
      resize.disconnect()
      el.removeEventListener('scroll', schedule, true)
      el.removeEventListener('toggle', schedule, true)
      el.dataset.companionTravel = 'false'
    }
  }, [
    root,
    state.sessionId,
    state.blank,
    state.pending,
    state.quiet,
    state.view,
    state.openState,
    followReply,
  ])
}
