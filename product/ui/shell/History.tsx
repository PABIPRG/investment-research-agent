import { useEffect, useRef } from 'react'
import type { ChatRuntime } from '../dsh-face.js'
import { historyRows } from '../history.js'
import css from './History.module.css'
import type { Actions } from './types.js'
import { beginHistoryTransition, captureCompanionOrigin } from './history-transition.js'
export function History(props: ChatRuntime & Actions & { close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null),
    list = props.useSessions((s) => s),
    workspaces = props.useWorkspaces((s) => s),
    connection = props.useConnectionState((s) => s)
  const selected = list.ids.find((id) => (list.byId[id]?.retainedBy?.mainView ?? 0) > 0)
  const rows = historyRows(
    list,
    workspaces.archivedSessionIds,
    selected,
    workspaces.phase === 'ready',
  )
  useEffect(() => {
    dialog.current?.showModal()
    return () => dialog.current?.close()
  }, [])
  return (
    <dialog
      ref={dialog}
      className={css.history}
      onCancel={props.close}
      onClick={(e) => {
        if (e.target === e.currentTarget) props.close()
      }}
      aria-labelledby="history-title"
    >
      <div>
        <header>
          <h2 id="history-title">历史对话</h2>
          <button onClick={props.close} aria-label="关闭历史对话">
            关闭
          </button>
        </header>
        {connection !== 'connected' ? (
          <p role="alert">
            连接暂不可用，历史可能过期。<button onClick={props.reconnect}>重新连接</button>
          </p>
        ) : null}
        {list.phase === 'pending' || workspaces.phase === 'pending' ? (
          <p role="status">正在读取历史…</p>
        ) : !rows.length ? (
          <p>暂无历史对话。</p>
        ) : (
          <ul>
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  aria-current={selected === row.id ? 'page' : undefined}
                  onClick={() => {
                    if (row.id !== selected)
                      beginHistoryTransition(
                        row.id,
                        captureCompanionOrigin(
                          dialog.current?.closest<HTMLElement>('[data-huohuo-conversation]') ??
                            null,
                        ),
                      )
                    props.openHistory(row.id)
                    props.close()
                  }}
                >
                  <strong>{row.label}</strong>
                  <small>
                    {row.running ? '进行中 · ' : ''}
                    {new Date(row.updatedAt).toLocaleString('zh-CN')}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </dialog>
  )
}
