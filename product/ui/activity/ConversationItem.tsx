import { conversationStates, type ConversationRow } from './conversation-model.js'
import { time } from '../model.js'
import css from './Sidebar.module.css'
export function ConversationItem({
  row,
  open,
}: {
  row: ConversationRow
  open: (id: string) => void
}) {
  return (
    <article className={css.task}>
      <span className={css.status} data-active={row.state === 'running' || undefined}>
        {conversationStates[row.state]}
      </span>
      <h3>{row.label}</h3>
      {row.kind === 'child' && <p>所属对话：{row.rootLabel}</p>}
      <small>最近记录 {time(row.updatedAt === undefined ? undefined : row.updatedAt / 1000)}</small>
      <button className={css.link} onClick={() => open(row.rootId)}>
        {row.kind === 'child' ? '查看所属对话' : '查看对话'}
      </button>
    </article>
  )
}
