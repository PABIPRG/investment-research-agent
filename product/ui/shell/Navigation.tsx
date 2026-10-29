import { useRef } from 'react'
import { SlidingPill } from '../shared/SlidingPill.js'
import { useActivity } from '../activity/store.js'
import css from './Root.module.css'
import type { Actions } from './types.js'

const NAV = [
  [null, '对话'],
  ['huohuo-research', '我的委托'],
  ['huohuo-activity', '动态'],
  ['huohuo-investment', '持仓与自选'],
  ['huohuo-evolution', '验证与演进'],
  ['huohuo-notifications', '提醒方式'],
] as const

export function Navigation({
  panel,
  select,
  variant = 'horizontal',
  className,
}: {
  panel: string | null
  select: Actions['select']
  variant?: 'horizontal' | 'drawer'
  className?: string
}) {
  const nav = useRef<HTMLElement>(null)
  const activity = useActivity()
  return (
    <nav ref={nav} className={className} aria-label={variant === 'drawer' ? '页面导航' : '主导航'}>
      {variant === 'horizontal' && <SlidingPill container={nav} selected={panel} />}
      {NAV.map(([id, title]) => (
        <button
          key={title}
          aria-current={panel === id ? 'page' : undefined}
          aria-label={
            id === 'huohuo-activity' && activity.count > 0
              ? `动态，${activity.count} 条新动态，本机查看记录`
              : undefined
          }
          onClick={() => select(id)}
        >
          {title}
          {id === 'huohuo-activity' && activity.count > 0 && (
            <span
              className={css.badge}
              title={`本机有 ${activity.count} 条新动态${activity.error ? '；刷新失败，显示上次结果' : ''}`}
              aria-hidden="true"
            >
              {activity.count > 99 ? '99+' : activity.count}
            </span>
          )}
        </button>
      ))}
    </nav>
  )
}
