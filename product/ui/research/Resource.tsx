import { useSnapshot } from '../shared/useSnapshot.js'
import { useEffect, useState } from 'react'
import { label, message, read, states } from '../model.js'
import css from '../Query.module.css'
import { ReadStatus } from '../shared/ReadStatus.js'
export interface Resource<T> {
  data?: T
  error?: string
  loading: boolean
  refreshing?: boolean
  refresh?: () => void
  at?: number
}

/** Component-local reads cancel on navigation and never overwrite a newer selection. */
export function useRead<T>(
  kind: Parameters<typeof read>[0],
  refresh: number,
  id?: string,
): Resource<T> {
  const snapshot = useSnapshot<T>(
    `${kind}:${id || ''}:${refresh}`,
    (signal) => read<T>(kind, signal, id),
    {
      pollMs: (value) => {
        const data = value as any
        return data.executions?.some((x: any) => ['queued', 'running'].includes(x.status)) ||
          ['queued', 'running'].includes(data.execution?.status)
          ? 3000
          : 60000
      },
    },
  )
  return { ...snapshot, at: snapshot.at || undefined }
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
      <ReadStatus loading={resource.loading} hasData={resource.data !== undefined} />
      {resource.error && (
        <p className={css.error} role="alert">
          {resource.error}
          {resource.data ? ' 当前保留上次成功读取的内容，可能已经过期。' : ''}
        </p>
      )}
      {resource.data !== undefined && !resource.error && empty && (
        <p className={css.empty}>{empty}</p>
      )}
    </>
  )
}
