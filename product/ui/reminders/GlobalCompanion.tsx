import { useReminderLayer } from './useReminderLayer.js'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Mascot } from '../shell/Mascot.js'
import { useCompanionPresentation } from '../shell/companion-presentation.js'
import { useReminders, respondReminder, reminderPresented, markReminderPresented } from './store.js'
import { ReminderCard } from './ReminderCard.js'
import { useActorPosition } from './useActorPosition.js'
import css from './Reminder.module.css'
export function GlobalCompanion({
  panel,
  select,
}: {
  panel: string | null
  select: (id: string | null) => void
}) {
  const chat = useCompanionPresentation(),
    reminders = useReminders()
  const item = reminders.owned ? reminders.pending[0] : undefined
  const actor = useRef<HTMLDivElement>(null),
    layer = useRef<HTMLDivElement>(null)
  const [phase, setPhase] = useState<'notice' | 'moving' | 'knocking' | 'waiting'>('notice')
  const phaseItem = useRef<string>()
  // A new queue head continues the same visit; do not send the actor home between cards.
  const shownPhase =
    item && phaseItem.current !== item.id ? (phaseItem.current ? 'waiting' : 'notice') : phase
  const [ready, setReady] = useState('loading')
  const [returning, setReturning] = useState(false)
  const previousItem = useRef(false)
  const reduced =
    typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
  useEffect(() => {
    if (!item || ready === 'loading') return
    const continuing = !!phaseItem.current && phaseItem.current !== item.id
    phaseItem.current = item.id
    if (continuing || reminderPresented(item.id)) {
      markReminderPresented(item.id)
      setPhase('waiting')
      return
    }
    setPhase('notice')
    const moving = !panel && chat.visible && !reduced
    const start = setTimeout(() => setPhase(moving ? 'moving' : 'knocking'), moving ? 100 : 0)
    const knock = setTimeout(
      () => {
        markReminderPresented(item.id)
        setPhase('knocking')
      },
      moving ? 550 : 0,
    )
    const wait = setTimeout(() => setPhase('waiting'), moving ? 4650 : 4100)
    return () => {
      clearTimeout(start)
      clearTimeout(knock)
      clearTimeout(wait)
    }
  }, [item?.id, ready])
  const chatVisible = panel === null && chat.visible
  // Keep the transition and top layer for the whole trip back, including the first render.
  const returningNow = !item && chatVisible && !reduced && (returning || previousItem.current)
  useLayoutEffect(() => {
    if (!item && previousItem.current && chatVisible && !reduced) setReturning(true)
    previousItem.current = !!item
    if (!item) phaseItem.current = undefined
  }, [item, chatVisible, reduced])
  useEffect(() => {
    if (!returning) return
    const end = setTimeout(() => setReturning(false), 450)
    return () => clearTimeout(end)
  }, [returning])
  const blocked = useReminderLayer(layer, !!item || returningNow)
  useActorPosition(actor, {
    reminder: !!item,
    corner: !!item && (shownPhase !== 'notice' || !chatVisible),
    chat: chatVisible,
    state: `${chat.motion}:${chat.arrival}`,
    ready,
  })
  const respond = () => {
    if (item) respondReminder(item.id)
  }
  const visit = () => {
    if (!item) return
    if (item.kind === 'mandate' && item.mandate_id) {
      sessionStorage.setItem(
        'huohuo-return',
        JSON.stringify({ mandate: item.mandate_id, decision: item.decision_id }),
      )
      select('huohuo-research')
      window.dispatchEvent(new CustomEvent('huohuo-mandate-view', { detail: item.mandate_id }))
    } else select('huohuo-notifications')
    respond()
  }
  return (
    <div
      ref={layer}
      className={css.layer}
      data-reminder-phase={item ? shownPhase : returningNow ? 'returning' : undefined}
    >
      <div
        ref={actor}
        className={css.actor}
        data-huohuo-global-companion
        data-moving={returningNow || (!!item && shownPhase === 'moving')}
        style={{ visibility: item || chatVisible ? undefined : 'hidden' }}
      >
        <Mascot
          motion={
            item ? (shownPhase === 'knocking' ? 'gentle_knock' : 'awaiting_reply') : chat.motion
          }
          arrival={!item && chat.arrival}
          visible={!!item || chatVisible}
          onState={setReady}
        />
      </div>
      {item && (
        <ReminderCard
          item={item}
          count={reminders.pending.length}
          blocked={blocked}
          respond={respond}
          visit={visit}
        />
      )}
    </div>
  )
}
