import { useRef } from 'react'
import { SlidingPill } from '../shared/SlidingPill.js'
import css from './Conversation.module.css'
export function ViewTabs({
  view,
  select,
}: {
  view: 'chat' | 'trajectory'
  select: (view: 'chat' | 'trajectory') => void
}) {
  const container = useRef<HTMLDivElement>(null)
  return (
    <div ref={container} className={css.viewTabs} aria-label="会话视图">
      <SlidingPill container={container} selected={view} />
      <button aria-pressed={view === 'chat'} onClick={() => select('chat')}>
        对话
      </button>
      <button aria-pressed={view === 'trajectory'} onClick={() => select('trajectory')}>
        轨迹
      </button>
    </div>
  )
}
