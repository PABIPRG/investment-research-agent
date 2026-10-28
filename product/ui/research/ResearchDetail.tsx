import { useEffect, useRef } from 'react'
import { researchQuestion, securityName } from '../business-model.js'
import {
  eventNames,
  label,
  time,
  type BusinessEvent,
  type Evidence,
  type Execution,
} from '../model.js'
import css from '../Query.module.css'
import { EvidenceView } from './EvidenceView.js'
import { Notice, State, useRead } from './Resource.js'
export function Detail({
  id,
  refresh,
  back,
  names,
}: {
  id: string
  refresh: number
  back: () => void
  names: Record<string, string>
}) {
  const task = useRead<Execution>('execution', refresh, id)
  const events = useRead<BusinessEvent[]>('events', refresh, id)
  const evidence = useRead<Evidence[]>('evidence', refresh, id)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [id])
  return (
    <section className={css.detail} aria-labelledby="huohuo-detail-title">
      <button className={css.textButton} onClick={back}>
        ← 返回列表
      </button>
      <h2 id="huohuo-detail-title" tabIndex={-1} ref={heading}>
        研究详情
      </h2>
      <Notice resource={task} />
      {task.data && (
        <>
          <div className={css.rowHeading}>
            <span className={css.note}>
              {securityName(
                task.data.scope.entity_id,
                names[task.data.scope.entity_id.split(':').at(-1)!],
                evidence.data?.find((e) => e.values?.name)?.values?.name,
              )}{' '}
              · {task.data.scope.entity_id.split(':').at(-1)}
            </span>
            <State value={task.data.status} />
          </div>
          <h3 className={css.question}>{researchQuestion(task.data.question)}</h3>
          <p className={css.note}>
            提交：{time(task.data.created_at)}
            <br />
            更新：{time(task.data.updated_at)}
          </p>
          <section className={css.section} aria-labelledby="huohuo-result-title">
            <h3 id="huohuo-result-title">研究结果</h3>
            {task.data.result?.summary ? (
              <p className={css.summary}>{task.data.result.summary}</p>
            ) : task.data.result?.error ? (
              <p className={css.error}>{task.data.result.error}</p>
            ) : (
              <p className={css.note}>
                {task.data.status === 'cancelled'
                  ? '这项研究已取消，没有可交付结果。'
                  : task.data.status === 'interrupted'
                    ? '执行已中断。可在对话中明确要求重试。'
                    : '尚无已保存的研究结果。'}
              </p>
            )}
          </section>
          <details className={css.meta}>
            <summary>排查信息（可选）</summary>
            <p>研究编号：{task.data.execution_id}</p>
            <p>当前修订：{task.data.revision}</p>
          </details>
        </>
      )}
      <section className={css.section} aria-labelledby="huohuo-events-title">
        <h3 id="huohuo-events-title">执行进展</h3>
        <p className={css.note}>这里记录后台已确认的关键进展。</p>
        <Notice
          resource={events}
          empty={events.data?.length === 0 ? '暂无执行事件。' : undefined}
        />
        <ol className={css.timeline}>
          {events.data?.map((event) => (
            <li key={event.seq}>
              <strong>{label(eventNames, event.kind, '其他业务事件')}</strong>
              <time>{time(event.created_at)}</time>
            </li>
          ))}
        </ol>
      </section>
      <section className={css.section} aria-labelledby="huohuo-evidence-title">
        <h3 id="huohuo-evidence-title">研究证据</h3>
        <Notice
          resource={evidence}
          empty={evidence.data?.length === 0 ? '尚无留存证据。' : undefined}
        />
        {evidence.data?.map((row) => (
          <EvidenceView
            key={row.evidence_id}
            row={row}
            current={
              !!task.data?.result?.evidence_ids?.includes(row.evidence_id) &&
              row.attempt_id === task.data.current_attempt
            }
          />
        ))}
      </section>
    </section>
  )
}
