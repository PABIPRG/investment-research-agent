import { useState } from 'react'
import { time } from '../model.js'
import type { ChangeGroup } from './group-changes.js'
import { channelLabels, deliveryLabels } from '../notifications/model.js'
import type { Change } from './dashboard-model.js'
import css from './Changes.module.css'
export function ChangeList({
  groups,
  visit,
}: {
  groups: readonly ChangeGroup[]
  visit: (mandate: string, decision: string, execution?: string) => void
}) {
  return (
    <div className={css.list}>
      {groups.map((group, i) => (
        <Group key={group.id} group={group} featured={i === 0} visit={visit} />
      ))}
    </div>
  )
}

function Group({
  group,
  featured,
  visit,
}: {
  group: ChangeGroup
  featured: boolean
  visit: (mandate: string, decision: string, execution?: string) => void
}) {
  const [limit, setLimit] = useState(5)
  const row = group.latest
  return (
    <article className={css.event} data-featured={featured || undefined}>
      <EventContent row={row} visit={visit} />
      {group.rows.length > 1 && (
        <details className={css.groupDetails}>
          <summary>
            已读取 {group.rows.length} 条研究记录
            {group.incomplete > 0 && ` · 其中 ${group.incomplete} 条未完成`}
            {group.uncertain > 0 && ` · ${group.uncertain} 条判断待核实`} · 查看记录
          </summary>
          <div className={css.groupRows}>
            {group.rows.slice(0, limit).map((entry) => (
              <article className={css.groupEntry} key={entry.id}>
                <EventContent row={entry} visit={visit} />
              </article>
            ))}
            {group.rows.length > limit && (
              <button type="button" onClick={() => setLimit((n) => n + 5)}>
                查看更多记录（还有 {group.rows.length - limit} 条）
              </button>
            )}
          </div>
        </details>
      )}
    </article>
  )
}
function EventContent({
  row,
  visit,
}: {
  row: Change
  visit: (mandate: string, decision: string, execution?: string) => void
}) {
  return (
    <>
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
              {channelLabels[r.channel] || '联系渠道'}：{deliveryLabels[r.status] || '状态待核对'}
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
    </>
  )
}
