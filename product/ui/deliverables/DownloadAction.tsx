import { useEffect, useRef, useState } from 'react'
import styles from './DownloadAction.module.css'

/** DSH 交付卡片动作：使用持久会话事件坐标，不从模型正文猜文件。 */
export function DownloadAction({ actionUrl }: { actionUrl: string }) {
  const [state, setState] = useState<'idle' | 'pending' | 'success' | 'error'>('idle')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => {
    setState('idle')
    return () => {
      controller.current?.abort()
      controller.current = null
    }
  }, [actionUrl])
  const download = async () => {
    if (controller.current) return
    const task = new AbortController()
    controller.current = task
    setState('pending')
    try {
      const coordinates = new URL(actionUrl, location.href).searchParams
      const response = await fetch(`/api/huohuo/deliverables/download?${coordinates}`, {
        signal: task.signal,
      })
      if (!response.ok) throw Error('download failed')
      const blob = await response.blob()
      task.signal.throwIfAborted()
      const encoded = response.headers
        .get('Content-Disposition')
        ?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
      if (!encoded) throw Error('filename missing')
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = decodeURIComponent(encoded)
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
      setState('success')
    } catch {
      if (!task.signal.aborted) setState('error')
    } finally {
      if (controller.current === task) controller.current = null
    }
  }
  return (
    <div className={styles.root}>
      <button type="button" disabled={state === 'pending'} onClick={() => void download()}>
        {state === 'pending' ? '下载中…' : state === 'error' ? '重试下载' : '下载'}
      </button>
      <span role="status" aria-live="polite">
        {state === 'error'
          ? '下载失败，请重试；成果可能已缺失。'
          : state === 'success'
            ? '已交给浏览器保存'
            : ''}
      </span>
    </div>
  )
}
