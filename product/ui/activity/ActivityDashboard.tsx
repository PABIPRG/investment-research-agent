import { useEffect, useState } from 'react'
import { useConversationProgress, type ConversationProgressProps } from './ConversationProgress.js'
import { useActivityMandates } from './useActivityMandates.js'
import { markActivitySeen, refreshActivity, useActivity } from './store.js'
import {
  dashboardEvents,
  mandateAttention,
  splitChanges,
  splitConversations,
} from './dashboard-model.js'
import { AttentionSection } from './AttentionSection.js'
import { FollowupProgress } from './FollowupProgress.js'
import { ChangeList } from './ChangeList.js'
import { ConversationItem } from './ConversationItem.js'
import { ReadStatus } from '../shared/ReadStatus.js'
import page from '../shared/Page.module.css'
import controls from '../shared/Controls.module.css'
import css from './Dashboard.module.css'
import { time } from '../model.js'
export type ActivityProps = ConversationProgressProps & {
  visit: (mandate: string, decision: string, execution?: string) => void
  allMandates: () => void
}
const filters = { all: '全部', research: '研究结果', reminder: '提醒' } as const
export function ActivityDashboard(props: ActivityProps) {
  const [refresh, setRefresh] = useState(0),
    [filter, setFilter] = useState<keyof typeof filters>('all'),
    [historyOpen, setHistoryOpen] = useState(false)
  const notifications = useActivity(),
    mandates = useActivityMandates(),
    conversations = useConversationProgress(props, refresh)
  const changes = splitChanges(
    dashboardEvents(mandates.items, notifications.items),
    Date.now() / 1000,
  )
  const groups = splitConversations(conversations.rows)
  const visible = changes.recent.filter((r) => filter === 'all' || r.kind === filter)
  const known =
    mandates.at > 0 &&
    !mandates.error &&
    mandates.complete &&
    conversations.ready &&
    conversations.complete &&
    !conversations.error
  const loading = (mandates.loading && !mandates.at) || !conversations.ready
  const shownRecords = [...visible, ...(historyOpen ? changes.history : [])].flatMap(
    (r) => r.records,
  )
  const shownKey = JSON.stringify(shownRecords)
  useEffect(() => {
    if (notifications.loaded && !notifications.error && !notifications.loading)
      markActivitySeen(JSON.parse(shownKey))
  }, [shownKey, notifications.loaded, notifications.error, notifications.loading])
  const manualRefreshing = notifications.refreshing || mandates.refreshing
  const reload = () => {
    void refreshActivity(true)
    mandates.refresh()
    setRefresh((n) => n + 1)
  }
  return (
    <main className={`${page.surface} ${controls.controls} ${css.root}`}>
      <div className={css.content}>
        <header className={css.header}>
          <div>
            <h1>动态</h1>
            <p>先看新变化，再看火火正在跟进的事。</p>
          </div>
          <div className={css.refresh}>
            <small>委托读取于 {time(mandates.at || undefined)}</small>
            <button
              onClick={reload}
              disabled={
                manualRefreshing ||
                (!notifications.loaded && notifications.loading) ||
                (!mandates.at && mandates.loading)
              }
              aria-busy={manualRefreshing}
            >
              <span
                className={css.refreshIcon}
                data-active={manualRefreshing || undefined}
                aria-hidden="true"
              >
                <svg viewBox="0 0 24 24">
                  <path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2" />
                </svg>
              </span>
              刷新动态
            </button>
            <span className={page.srOnly} role="status">
              {manualRefreshing ? '正在刷新动态，保留已有内容。' : ''}
            </span>
          </div>
        </header>
        <AttentionSection
          conversations={groups.attention}
          mandates={mandateAttention(mandates.items)}
          certain={known}
          stale={!!mandates.error}
          loading={loading}
          openConversation={props.openConversation}
          visit={props.visit}
        />
        {(!conversations.connected ||
          conversations.error ||
          (conversations.ready && !conversations.complete)) && (
          <p role="status" className={css.warning}>
            {!conversations.connected
              ? '对话连接暂不可用，当前对话状态待核对。'
              : '部分对话与子任务状态尚未读全。'}{' '}
            可刷新动态重新核对。
          </p>
        )}
        <div className={css.layout}>
          <section className={css.feed} aria-labelledby="activity-changes-title">
            <div className={css.feedHead}>
              <div className={css.sectionHeader}>
                <h2 id="activity-changes-title">最新变化</h2>
                <span>
                  最近 48 小时{mandates.at > 0 && !mandates.complete ? ' · 已读取范围' : ''}
                </span>
              </div>
              <div className={css.filters} role="group" aria-label="筛选最新变化">
                {Object.entries(filters).map(([key, label]) => (
                  <button
                    key={key}
                    aria-pressed={filter === key}
                    onClick={() => setFilter(key as keyof typeof filters)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <ReadStatus
              loading={
                (notifications.loading && !notifications.loaded) ||
                (mandates.loading && !mandates.at)
              }
              hasData={visible.length > 0}
              label="正在读取研究结果与提醒…"
            />
            {notifications.error && (
              <p role="alert" className={css.readError}>
                {notifications.error}{' '}
                {notifications.loaded ? '保留上次读取的提醒，可能过期。' : '研究结果仍可独立查看。'}
              </p>
            )}
            {mandates.error && (
              <p role="alert" className={css.readError}>
                {mandates.error}{' '}
                {mandates.at ? '保留上次读取的研究结果，可能过期。' : '提醒记录仍可独立查看。'}
              </p>
            )}
            {mandates.at > 0 && !mandates.complete && (
              <p className={css.readError} role="status">
                当前委托记录尚未读全，仅展示已读取范围，不能据此判断全部待办或变化。
              </p>
            )}
            <ChangeList rows={visible} visit={props.visit} />
            {!visible.length &&
              notifications.loaded &&
              !!mandates.at &&
              !notifications.error &&
              !mandates.error && (
                <div className={css.empty}>
                  <span aria-hidden="true">✓</span>
                  <h3>
                    {!mandates.complete
                      ? '已读取范围内暂无此类新变化'
                      : filter === 'all'
                        ? '最近 48 小时暂无新变化'
                        : `最近 48 小时暂无${filters[filter]}`}
                  </h3>
                  <p>有新结果或提醒时会显示在这里，仍可查看火火正在跟进的委托。</p>
                  {filter !== 'all' && (
                    <button onClick={() => setFilter('all')}>查看全部变化</button>
                  )}
                </div>
              )}
          </section>
          <FollowupProgress
            items={mandates.items}
            loading={mandates.loading}
            error={mandates.error}
            readAt={mandates.at}
            conversations={groups.running}
            uncertain={groups.uncertain}
            openConversation={props.openConversation}
            visit={props.visit}
            allMandates={props.allMandates}
          />
        </div>
        <details
          className={css.history}
          onToggle={(event) => setHistoryOpen(event.currentTarget.open)}
        >
          <summary>
            历史记录<small>较早变化与未运行的对话</small>
          </summary>
          <div className={css.historyContent}>
            <ChangeList rows={changes.history} visit={props.visit} />
            {groups.history.map((row) => (
              <ConversationItem key={row.id} row={row} open={props.openConversation} />
            ))}
            {!changes.history.length &&
              !groups.history.length &&
              known &&
              notifications.loaded &&
              !notifications.error && <p className={css.muted}>暂无已读取的历史记录。</p>}
            <p className={css.muted}>“当前未运行”不代表已完成。时间无法确认的变化也保留在这里。</p>
          </div>
        </details>
        <footer className={css.footnote}>
          按处理优先级组织；变化按时间倒序展示。未知状态不会当作零项或已完成。
        </footer>
      </div>
    </main>
  )
}
