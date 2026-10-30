import { time } from '../model.js'
import { channelLabels, deliveryLabels } from '../notifications/model.js'
import type { Change } from './dashboard-model.js'
import css from './Changes.module.css'
export function ChangeList({
  rows,
  visit,
}: {
  rows: readonly Change[]
  visit: (mandate: string, decision: string, execution?: string) => void
}) {
  return (
    <div className={css.list}>
      {rows.map((row, i) => (
        <article className={css.event} data-featured={i === 0 || undefined} key={row.id}>
          <div className={css.meta}>
            <span>{row.kind === 'research' ? '研究结果' : '提醒记录'}</span>
            <time>{time(row.at)}</time>
          </div>
          <h3>{row.title}</h3>
          <p className={css.summary}>{row.summary}</p>
          {(row.evidenceCount !== undefined || row.warning) && (
            <div className={css.tags}>
              {row.evidenceCount !== undefined && (
                <span>
                  {row.evidenceCount > 0 ? `${row.evidenceCount} 条引用依据` : '未附引用依据'}
                </span>
              )}
              {row.warning && <span className={css.warning}>{row.warning}</span>}
            </div>
          )}
          {row.records.length > 0 && (
            <div className={css.receipts}>
              {row.records.map((r) => (
                <span key={`${r.channel}:${r.status}`}>
                  {channelLabels[r.channel] || '联系渠道'}：
                  {deliveryLabels[r.status] || '状态待核对'}
                  {r.detail ? `（${r.detail}）` : ''}
                </span>
              ))}
            </div>
          )}
          <footer>
            <span>来自「{row.source}」</span>
            <button onClick={() => visit(row.mandateId, row.decisionId, row.executionId)}>
              {row.kind === 'research' ? '查看结果与依据' : '查看提醒与依据'}
              <span aria-hidden="true">→</span>
            </button>
          </footer>
        </article>
      ))}
    </div>
  )
}
