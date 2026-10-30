import { useSnapshot } from './shared/useSnapshot.js'
import { request } from './shared/api.js'
import { ReadFeedback } from './shared/ReadFeedback.js'
import {
  ConversationProgress,
  type ConversationProgressProps,
} from './activity/ConversationProgress.js'
import type { MandateView } from './mandates/model.js'
import { FollowupProgress } from './activity/FollowupProgress.js'
import page from './shared/Page.module.css'
import { ReadStatus } from './shared/ReadStatus.js'
import { useEffect, useState } from 'react'
import { markActivitySeen, refreshActivity, useActivity } from './activity/store.js'
import { mandateName } from './business-model.js'
import css from './Business.module.css'
import { time } from './model.js'
import { channelLabels, decisionText, deliveryLabels } from './notifications/model.js'
export function ActivityPage(
  props: ConversationProgressProps & { visit: (mandate: string, decision: string) => void },
) {
  const { visit } = props
  const { items, error: activityError, loading, loaded, refreshing } = useActivity()
  const [refresh, setRefresh] = useState(0)
  const details = useSnapshot<{ items: MandateView[] }>(
    'activity-mandates',
    (signal) => request('mandates', undefined, signal),
    { pollMs: () => 30000 },
  )
  const mandates = details.data?.items ?? [],
    error = details.error,
    detailsLoading = details.loading,
    readAt = details.at
  useEffect(() => {
    if (!loading && !detailsLoading && !activityError && !error) markActivitySeen(items)
  }, [items, loading, detailsLoading, activityError, error])
  const failure = activityError
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header}`}>
        <div>
          <h1>动态</h1>
          <p className={css.note}>查看委托的跟进进展与已保存提醒</p>
        </div>
        <button
          onClick={() => {
            void refreshActivity(true)
            details.refresh()
            setRefresh((n) => n + 1)
          }}
          disabled={loading || detailsLoading || refreshing || details.refreshing}
        >
          刷新动态
        </button>
      </header>
      <ConversationProgress {...props} refresh={refresh} />
      <FollowupProgress
        items={mandates}
        loading={detailsLoading}
        error={error}
        readAt={readAt}
        visit={visit}
      />
      <h2>提醒记录</h2>
      <p className={css.note}>{items.length} 条已保存联系记录 · 可回到委托核对依据</p>
      <ReadStatus loading={loading} hasData={loaded} />
      <ReadFeedback error={failure} />
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              {['类型 / 时间', '相关委托', '内容与限制', '操作'].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loaded && !failure && !items.length && (
              <tr>
                <td colSpan={4} className={css.empty}>
                  暂无提醒记录。委托有需要联系你的结果后，会显示在这里；这不代表后台没有研究任务。
                </td>
              </tr>
            )}
            {items.map((row) => {
              const mandate = mandates.find((m) => m.mandate.mandate_id === row.mandate_id)
              return (
                <tr key={`${row.decision_id}:${row.channel}`}>
                  <td>
                    {channelLabels[row.channel] || '联系记录'}
                    <small>{time(row.created_at ?? row.updated_at)}</small>
                  </td>
                  <td>
                    <strong>{mandate ? mandateName(mandate) : '委托信息暂未读取'}</strong>
                    <small>{mandate?.revision.goal}</small>
                  </td>
                  <td>
                    {decisionText(row.decision_detail || '', row.reason_code || '')}
                    <small>
                      {deliveryLabels[row.status] || '状态待核对'} · {row.detail}
                    </small>
                  </td>
                  <td>
                    <button onClick={() => visit(row.mandate_id, row.decision_id)}>
                      看委托与依据
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </main>
  )
}
export function PlannedPage({ kind }: { kind: 'framework' | 'evolution' }) {
  const framework = kind === 'framework'
  const headers = framework
    ? ['内容', '当前生效表述', '依据', '版本 / 日期', '操作']
    : ['候选改动', '对照与范围', '验证结果 / 限制', '状态', '操作']
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header}`}>
        <div>
          <h1>{framework ? '我的框架' : '验证与演进'}</h1>
          <p className={css.note}>{framework ? '明确偏好、判断与约定' : '候选与生效分开'}</p>
        </div>
      </header>
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              {headers.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} className={css.empty}>
                {framework
                  ? '框架记录尚未接入，暂不能读取或修改已确认的研究方法。'
                  : '验证记录尚未接入，暂不能查看对照、采用候选或回查修订。'}
                <small>此处没有可用数据，不代表你没有框架或验证记录。</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className={css.note}>
        {framework
          ? '推测兴趣不写入明确偏好；候选调整在验证与演进中单独确认。'
          : '未经验证与确认的候选不作为已生效规则。'}
      </p>
    </main>
  )
}
