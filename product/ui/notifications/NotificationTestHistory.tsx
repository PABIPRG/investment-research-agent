import { useEffect, useState } from 'react'
import { request, errorText } from '../shared/api.js'
import { channelLabels } from './model.js'
import { testStatuses, type NotificationTest } from './test-model.js'
import css from '../Query.module.css'
export function NotificationTestHistory({ refresh }: { refresh: number }) {
  const [rows, setRows] = useState<NotificationTest[]>(),
    [error, setError] = useState('')
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    request<{ items: NotificationTest[] }>('notification-tests', undefined, abort.signal)
      .then((r) => {
        if (!abort.signal.aborted) setRows(r.items)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
    return () => abort.abort()
  }, [refresh])
  return (
    <details className={css.section}>
      <summary>测试提醒记录 · {rows?.length ?? '—'} 条</summary>
      <p className={css.note}>
        这里只记录手动测试，应用内测试也保存在这里；与正式委托提醒分开。最近最多20条。
      </p>
      {error && <p role="alert">{error} 已显示内容可能过期。</p>}
      {rows?.length === 0 && <p>尚未发送过测试提醒。</p>}
      {rows?.map((r) => (
        <article className={css.evidence} key={r.test_id}>
          <h3>
            {channelLabels[r.channel]} · {testStatuses[r.status] || '状态待核对'}
          </h3>
          <p>
            {r.target_summary} ·{' '}
            {new Date(r.created_at * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}
          </p>
          <p>{r.detail}</p>
          <small>手动测试 · 忽略静默时间</small>
        </article>
      ))}
    </details>
  )
}
