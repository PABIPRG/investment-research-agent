import type { Attention } from './dashboard-model.js'
import type { ConversationRow } from './conversation-model.js'
import css from './Attention.module.css'
export function AttentionSection({
  conversations,
  mandates,
  certain,
  stale,
  loading,
  openConversation,
  visit,
}: {
  conversations: ConversationRow[]
  mandates: Attention[]
  certain: boolean
  stale: boolean
  loading: boolean
  openConversation: (id: string) => void
  visit: (mandate: string, decision: string) => void
}) {
  const rows = [
    ...conversations.map((r) => ({
      id: r.id,
      blocked: false,
      title: `${r.label}：等待你的回答或确认`,
      source: r.rootLabel,
      detail:
        r.kind === 'child'
          ? `请回到所属对话「${r.rootLabel}」处理。`
          : '火火正在等待你的选择，请回到原对话查看具体问题。',
      action: '查看并回答',
      run: () => openConversation(r.rootId),
    })),
    ...mandates.map((r) => ({
      ...r,
      source: r.source,
      blocked: stale,
      run: () => visit(r.mandateId, ''),
    })),
  ]
  if (!rows.length)
    return (
      <div className={css.quiet} role="status">
        <span className={css.quietMark}>{certain ? '✓' : '—'}</span>
        <span>
          {certain
            ? '当前没有需要你处理的事项'
            : loading
              ? '正在核对需要你处理的事项…'
              : '部分状态待核对，暂不能确认是否有待处理事项'}
        </span>
        <small>{certain ? '有需要时，会优先显示在这里' : '可刷新动态重新核对'}</small>
      </div>
    )
  const content = (row: (typeof rows)[number], i: number) => (
    <article className={i === 0 ? css.attentionRow : css.otherAttention} key={row.id}>
      <div>
        <h3 title={row.title}>{row.title}</h3>
        <p>{row.detail}</p>
        <small className={css.source}>来自「{row.source}」</small>
      </div>
      <button
        className={i === 0 ? css.primary : css.secondary}
        disabled={row.blocked}
        onClick={row.run}
      >
        {row.action}
        <span aria-hidden="true">→</span>
      </button>
    </article>
  )
  return (
    <section className={css.attention} aria-label="需要你处理">
      <div className={css.attentionLabel}>
        需要你处理 <span>{certain ? rows.length : `至少 ${rows.length}`} 项</span>
      </div>
      {stale && (
        <p role="status" className={css.warning}>
          委托资料可能过期，请先刷新，再处理相关事项。
        </p>
      )}
      {rows.slice(0, 3).map(content)}
      {rows.length > 3 && (
        <details className={css.more}>
          <summary>还有 {rows.length - 3} 项待处理</summary>
          {rows.slice(3).map((row, i) => content(row, i + 3))}
        </details>
      )}
    </section>
  )
}
