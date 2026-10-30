import type { MandateView } from '../mandates/model.js'
import type { ConversationRow } from './conversation-model.js'
import { mandateName } from '../business-model.js'
import { time } from '../model.js'
import { mandateAttention } from './dashboard-model.js'
import { followupProgress, progressLabels } from './followup.js'
import { ConversationItem } from './ConversationItem.js'
import css from './Sidebar.module.css'
export function FollowupProgress({
  items,
  loading,
  error,
  readAt,
  visit,
  conversations,
  uncertain,
  openConversation,
  allMandates,
}: {
  items: MandateView[]
  loading: boolean
  error: string
  readAt: number
  visit: (mandate: string, decision: string) => void
  conversations: ConversationRow[]
  uncertain: ConversationRow[]
  openConversation: (id: string) => void
  allMandates: () => void
}) {
  const attentionIds = new Set(mandateAttention(items).map((row) => row.mandateId))
  const rows = followupProgress(items).filter(
    (row) => !attentionIds.has(row.item.mandate.mandate_id),
  )
  return (
    <aside>
      <section className={css.panel} aria-labelledby="activity-followup-title" aria-busy={loading}>
        <header>
          <h2 id="activity-followup-title">正在跟进</h2>
          <small>{error || !readAt ? '状态待核对' : `${rows.length} 项委托`}</small>
        </header>
        <p className={css.caption}>
          {error ? `上次读取 ${time(readAt)} · 可能过期` : '持续委托与对话的当前进度'}
        </p>
        {loading && !readAt && <p role="status">正在读取跟进进展…</p>}
        {error && (
          <p className={css.warning} role="alert">
            {error} {readAt ? '以下保留上次读取的记录。' : '暂不能确认当前安排。'}
          </p>
        )}
        {conversations.map((row) => (
          <ConversationItem key={row.id} row={row} open={openConversation} />
        ))}
        {rows.slice(0, 6).map((row) => (
          <article className={css.task} key={row.item.mandate.mandate_id}>
            <span
              className={css.status}
              data-active={(!error && row.kind === 'running') || undefined}
            >
              {error ? '上次记录：' : ''}
              {progressLabels[row.kind]}
            </span>
            <h3>{mandateName(row.item)}</h3>
            <p className={css.goal}>{row.item.revision.goal}</p>
            <p>{row.detail}</p>
            {row.updatedAt && <small>记录于 {time(row.updatedAt)}</small>}
            <button className={css.link} onClick={() => visit(row.item.mandate.mandate_id, '')}>
              查看委托
            </button>
          </article>
        ))}
        {!rows.length && readAt > 0 && !error && !conversations.length && (
          <p className={css.empty}>暂无持续跟进的委托或正在处理的对话。</p>
        )}
        {rows.length > 6 && <p className={css.caption}>这里展示前 6 项，其余可在我的委托查看。</p>}
        {uncertain.length > 0 && (
          <details className={css.uncertain}>
            <summary>有 {uncertain.length} 项对话状态需核对</summary>
            {uncertain.map((row) => (
              <ConversationItem key={row.id} row={row} open={openConversation} />
            ))}
          </details>
        )}
        <button className={css.all} onClick={allMandates}>
          查看全部委托<span aria-hidden="true">›</span>
        </button>
      </section>
      <p className={css.note}>
        “等待下次跟进”表示安排仍保留，不代表研究正在运行。进度来自已保存的任务记录。
      </p>
    </aside>
  )
}
