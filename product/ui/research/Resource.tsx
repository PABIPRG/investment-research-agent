import { useEffect, useState } from 'react'
import { label, message, read, states } from '../model.js'
import css from '../Query.module.css'
export interface Resource<T> {
  data?: T
  error?: string
  loading: boolean
  at?: number
}

/** Component-local reads cancel on navigation and never overwrite a newer selection. */
export function useRead<T>(
  kind: Parameters<typeof read>[0],
  refresh: number,
  id?: string,
): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ loading: true })
  useEffect(() => {
    const controller = new AbortController()
    setState((old) => ({ ...old, loading: true, error: undefined }))
    void read<T>(kind, controller.signal, id)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, loading: false, at: Date.now() / 1000 })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState((old) => ({ ...old, error: message(error), loading: false }))
      })
    return () => controller.abort()
  }, [kind, id, refresh])
  return state
}
export function State({ value }: { value: string }) {
  return (
    <span className={css.status} data-state={value}>
      {label(states, value, '未知状态')}
    </span>
  )
}
export function Notice({ resource, empty }: { resource: Resource<unknown>; empty?: string }) {
  return (
    <>
      {resource.loading && (
        <p className={css.note} role="status">
          {resource.data ? '正在刷新，暂时保留上次读取的内容…' : '正在读取…'}
        </p>
      )}
      {resource.error && (
        <p className={css.error} role="alert">
          {resource.error}
          {resource.data ? ' 当前保留上次成功读取的内容，可能已经过期。' : ''}
        </p>
      )}
      {!resource.loading && !resource.error && empty && <p className={css.empty}>{empty}</p>}
    </>
  )
}
