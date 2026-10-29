import { useEffect, useState, useSyncExternalStore } from 'react'
import type { ChatRuntime, DshUiContext } from '../dsh-face.js'
import { conversationProgress, conversationStates } from './conversation-model.js'
import css from '../Business.module.css'
import local from './Progress.module.css'
export type ConversationProgressProps = Pick<
  ChatRuntime,
  'useSessions' | 'useSessionStatus' | 'useWorkspaces'
> & {
  connectionState: DshUiContext['connection']['state']
  openConversation: (id: string) => void
  refreshConversations: (ids: string[]) => Promise<void>
}
export function ConversationProgress(props: ConversationProgressProps & { refresh: number }) {
  const list = props.useSessions((s) => s),
    statuses = props.useSessionStatus((s) => s),
    connection = useSyncExternalStore(
      (fn) => props.connectionState.subscribe(fn),
      () => props.connectionState.getSnapshot(),
    ),
    workspaces = props.useWorkspaces((s) => s)
  const [error, setError] = useState(false)
  const model = conversationProgress(list, statuses, {
    connected: connection === 'connected',
    archiveReady: workspaces.phase === 'ready',
    archived: workspaces.archivedSessionIds,
  })
  const key = JSON.stringify(model.refreshIds)
  useEffect(() => {
    if (connection !== 'connected' || !model.ready) return
    let active = true
    setError(false)
    void props.refreshConversations(JSON.parse(key)).catch(() => {
      if (active) setError(true)
    })
    return () => {
      active = false
    }
  }, [connection, model.ready, key, props.refresh])
  const active = model.rows.filter((r) => r.state === 'running'),
    waiting = model.rows.filter((r) => r.state === 'waiting_user')
  const childrenRunning = active.filter((r) => r.kind === 'child').length
  const knownCount = (n: number) => (model.complete ? n : n ? `至少${n}` : '—')
  return (
    <section className={local.root} aria-label="对话与小火火进展">
      <header className={local.heading}>
        <h2>对话与小火火</h2>
        <span className={css.note}>随对话状态更新</span>
      </header>
      <p className={css.note}>
        查看对话正在处理的工作，以及已分派子任务的记录。当前版本尚未开放在对话中分派小火火。
      </p>
      {!model.ready ? (
        <p role="status">正在读取对话与子任务…</p>
      ) : (
        <>
          {connection !== 'connected' && (
            <p role="alert">连接暂不可用，无法确认当前是否仍在运行；下方保留已有记录。</p>
          )}
          {(error || !model.complete) && connection === 'connected' && (
            <p role="status">部分子任务状态尚未读全。可点击“刷新动态”重新核对。</p>
          )}
          <div className={css.metrics}>
            <span>
              对话处理中
              <b>
                {connection === 'connected'
                  ? active.filter((r) => r.kind === 'conversation').length
                  : '—'}
              </b>
            </span>
            <span>
              小火火处理中
              <b>{knownCount(childrenRunning)}</b>
            </span>
            <span>
              等你确认<b>{connection === 'connected' ? knownCount(waiting.length) : '—'}</b>
            </span>
          </div>
          {model.rows.slice(0, 20).map((row) => (
            <article className={local.item} key={row.id}>
              <div>
                <strong>{row.label}</strong>
                <span className={local.state}>{conversationStates[row.state]}</span>
                <p className={css.note}>
                  {row.kind === 'child'
                    ? `小火火／子任务 · 所属对话：${row.rootLabel}`
                    : '火火对话'}
                </p>
                {row.updatedAt !== undefined && (
                  <small>
                    最近记录{' '}
                    {new Date(row.updatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
                  </small>
                )}
              </div>
              <button onClick={() => props.openConversation(row.rootId)}>
                {row.kind === 'child' ? '查看所属对话' : '查看对话'}
              </button>
            </article>
          ))}
          {!model.rows.length && connection === 'connected' && (
            <p>暂无可展示的对话或子任务记录。</p>
          )}
          {model.rows.length > 20 && (
            <p className={css.note}>
              展示前20项，优先显示运行中或等待确认的工作；其余可从所属对话查看。
            </p>
          )}
          <p className={css.note}>
            “当前未运行”不代表已完成。只有保存了正常结束记录，才显示“本轮已完成”。
          </p>
        </>
      )}
    </section>
  )
}
