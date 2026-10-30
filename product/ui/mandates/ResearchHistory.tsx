import { time } from '../model.js'
import { EvidenceCard } from '../shared/EvidenceCard.js'
import { researchFinding } from '../shared/evidence-display.js'
import css from '../Query.module.css'
import { statuses, type MandateView } from './model.js'
export function ResearchHistory({
  current,
  returnExecution,
}: {
  current: MandateView
  returnExecution?: string
}) {
  if (!current.executions.length)
    return <p className={css.note}>尚未开始研究，有结果后可在这里查看内容和依据。</p>
  return (
    <section aria-label="每次研究的内容与依据">
      {current.executions.map((x) => {
        const finding = researchFinding(x.result)
        const evidence = current.evidence.filter((e) =>
          x.result?.evidence_ids?.includes(e.evidence_id),
        )
        const pending = ['queued', 'running'].includes(x.status)
        return (
          <article
            className={css.evidence}
            key={x.execution_id}
            id={`execution-${x.execution_id}`}
            tabIndex={-1}
            aria-label={x.execution_id === returnExecution ? '本次回访的研究记录' : '研究记录'}
          >
            <div className={css.rowHeading}>
              <strong>{pending ? statuses[x.status] : finding.title}</strong>
              <time className={css.note}>{time(x.updated_at)}</time>
            </div>
            <p>{pending ? '研究结果尚未生成，完成后再查看结论。' : finding.detail}</p>
            <p className={css.note}>
              {statuses[x.status] || '状态待核对'}
              {current.baseline?.execution_id === x.execution_id
                ? ' · 当前用于后续比较的参照结果'
                : ''}{' '}
              · {evidence.length} 份引用资料
            </p>
            <details className={css.readMore} open={x.execution_id === returnExecution}>
              <summary>查看这次研究的内容与依据</summary>
              <div className={css.readBody}>
                <h4>保存的研究摘要</h4>
                <p>{x.result?.summary || x.result?.error || '本次没有保存研究摘要。'}</p>
                <h4>本次引用资料</h4>
                {evidence.length ? (
                  evidence.map((row) => <EvidenceCard key={row.evidence_id} row={row} />)
                ) : (
                  <p className={css.note}>本次没有关联到可展示的资料。</p>
                )}
                <details className={css.meta}>
                  <summary>排查信息（可选）</summary>
                  <p>研究编号：{x.execution_id}</p>
                </details>
              </div>
            </details>
          </article>
        )
      })}
    </section>
  )
}
