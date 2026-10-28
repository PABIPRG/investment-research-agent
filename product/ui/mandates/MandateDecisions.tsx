import { time } from '../model.js'
import { channelLabels, decisionText, deliveryLabels } from '../notifications/model.js'
import { EvidenceCard } from '../shared/EvidenceCard.js'
import { judgementLabels, sourceName } from '../shared/evidence-display.js'
import css from '../Query.module.css'
import { sourceReason, type MandateView } from './model.js'
import { contactOutcome, decisionContext } from './readable-model.js'
export function MandateDecisions({
  current,
  returnDecision,
}: {
  current: MandateView
  returnDecision?: string
}) {
  return (
    <section aria-label="复核与提醒记录">
      {current.source_check && current.source_check.status !== 'ok' && (
        <p className={css.note}>最近资料检查：{sourceReason(current.source_check.detail)}</p>
      )}
      {!current.decisions?.length && <p className={css.note}>还没有复核与提醒记录。</p>}
      {current.decisions?.map((d) => {
        const linked = decisionContext(current, d)
        const reason = linked.result?.judgements?.notable_change?.reason
        return (
          <article
            className={css.evidence}
            key={d.decision_id}
            id={d.decision_id}
            tabIndex={-1}
            aria-label={d.decision_id === returnDecision ? '本次回访的复核记录' : '复核记录'}
          >
            <div className={css.rowHeading}>
              <strong>
                {d.reason_code === 'scheduled_delivery'
                  ? '定时研究已完成'
                  : d.reason_code === 'due_reminder'
                    ? '已到约定提醒时间'
                    : judgementLabels[d.condition_result] || '判断状态待核对'}
              </strong>
              <time className={css.note}>{time(d.created_at)}</time>
            </div>
            <p>{reason || decisionText(d.detail, d.reason_code)}</p>
            <p className={css.note}>提醒处理：{contactOutcome(d.decision)}</p>
            {linked.evidence.length ? (
              <details className={css.readMore}>
                <summary>查看本次依据 · {linked.evidence.length} 份资料</summary>
                <div className={css.readBody}>
                  {linked.evidence.map((row) => (
                    <EvidenceCard key={row.evidence_id} row={row} />
                  ))}
                </div>
              </details>
            ) : (
              <p className={css.note}>这条记录暂未关联到可展示的具体资料，无法核对其依据。</p>
            )}
            {linked.missing && (
              <p className={css.note}>部分引用资料缺失，当前仅显示已找到的内容。</p>
            )}
            <details className={css.meta}>
              <summary>排查信息（可选）</summary>
              <p>复核编号：{d.decision_id}</p>
              <p>依据引用：{d.evidence_ref || '未提供'}</p>
            </details>
          </article>
        )
      })}
      {current.notifications?.map((n) => (
        <p key={`${n.decision_id}:${n.channel}`}>
          {channelLabels[n.channel] || '联系渠道'} · {deliveryLabels[n.status] || '送达状态待核对'}
        </p>
      ))}
      {!!current.sources?.length && (
        <details className={css.meta}>
          <summary>资料检查记录 · {current.sources.length} 次</summary>
          <p>以下为系统获取资料的时间，不是公告发布时间。</p>
          {current.sources.map((src) => (
            <p key={src.event_id}>
              {sourceName(src.source)} · {time(src.observed_at)}
            </p>
          ))}
        </details>
      )}
    </section>
  )
}
