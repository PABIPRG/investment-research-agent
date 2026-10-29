import type { MandateView } from '../mandates/model.js'
import { mandateName } from '../business-model.js'
import { time } from '../model.js'
import { followupProgress, progressLabels } from './followup.js'
import css from '../Business.module.css'
import local from './Progress.module.css'
export function FollowupProgress({
  items,
  loading,
  error,
  readAt,
  visit,
}: {
  items: MandateView[]
  loading: boolean
  error: string
  readAt: number
  visit: (mandate: string, decision: string) => void
}) {
  const rows = followupProgress(items)
  return (
    <section className={local.root} aria-label="委托跟进进展" aria-busy={loading}>
      <header className={local.heading}>
        <h2>火火在跟进什么</h2>
        <span className={css.note}>
          {readAt ? `最近读取 ${time(readAt)}` : '正在读取跟进进展…'}
        </span>
      </header>
      <p className={css.note}>研究进展与提醒分开显示；没有新提醒，也可以在这里查看跟进安排。</p>
      {error && (
        <p role="alert">
          {error} {readAt ? '当前显示上次读取结果，可能过期。' : '暂不能确认跟进状态。'}
        </p>
      )}
      {readAt > 0 && (
        <>
          <div className={css.metrics}>
            {Object.entries(progressLabels).map(([kind, label]) => {
              const count = rows.filter((r) => r.kind === kind).length
              return count > 0 || ['running', 'queued', 'waiting'].includes(kind) ? (
                <span key={kind}>
                  {label}
                  <b>{count}</b>
                </span>
              ) : null
            })}
          </div>
          {rows.slice(0, 20).map((row) => (
            <article className={local.item} key={row.item.mandate.mandate_id}>
              <div>
                <strong>{mandateName(row.item)}</strong>
                <span className={local.state}>{progressLabels[row.kind]}</span>
                <p className={css.note}>{row.item.revision.goal}</p>
                <p>{row.detail}</p>
                {row.updatedAt && <small>任务状态更新于 {time(row.updatedAt)}</small>}
              </div>
              <button onClick={() => visit(row.item.mandate.mandate_id, '')}>查看委托</button>
            </article>
          ))}
          {!rows.length && !error && (
            <p>还没有持续跟进的委托。已暂停或结束的委托，可到“我的委托”查看。</p>
          )}
          {rows.length > 20 && <p className={css.note}>此处展示前20项，其余可到“我的委托”查看。</p>}
        </>
      )}
      {readAt > 0 && (
        <p className={css.note}>
          停留在本页时每30秒更新。 这里展示已保存的任务记录，不代表后台服务的实时在线状态。
        </p>
      )}
    </section>
  )
}
