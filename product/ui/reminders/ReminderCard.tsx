import type { Reminder } from './model.js'
import css from './Reminder.module.css'
export function ReminderCard({
  item,
  count,
  blocked,
  respond,
  visit,
}: {
  item: Reminder
  count: number
  blocked: boolean
  respond: () => void
  visit: () => void
}) {
  return (
    <aside
      className={css.card}
      data-huohuo-reminder
      aria-label={item.kind === 'test' ? '应用内测试提醒' : '火火提醒'}
    >
      <div className={css.heading}>
        <strong>{item.kind === 'test' ? '测试提醒' : '火火有事找你'}</strong>
        <button type="button" onClick={respond} aria-label="关闭这条提醒">
          ×
        </button>
      </div>
      <div role="status" aria-live="polite">
        <h2>{item.title}</h2>
        <p>{item.body}</p>
      </div>
      {blocked && <p>当前有操作窗口，关闭后可查看详情；也可以先收起这条提醒。</p>}
      <footer>
        <button type="button" disabled={blocked} onClick={visit}>
          {item.kind === 'test' ? '查看测试记录' : '查看委托与依据'}
        </button>
        <button type="button" onClick={respond}>
          稍后看
        </button>
        {count > 1 && <small>另有 {count - 1} 条</small>}
      </footer>
    </aside>
  )
}
