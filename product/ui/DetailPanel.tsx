import controls from './shared/Controls.module.css'
import { useEffect, useRef, type ReactNode } from 'react'
import css from './Business.module.css'
/** Native dialog owns focus trapping and returns focus to the invoking control. */
export function DetailPanel({
  title,
  close,
  children,
  compact = false,
}: {
  title: string
  close: () => void
  children: ReactNode
  compact?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog?.showModal()
    return () => {
      dialog?.close()
      queueMicrotask(() => {
        if (trigger?.isConnected) trigger.focus()
      })
    }
  }, [])
  return (
    <dialog
      ref={ref}
      className={`${css.dialog} ${controls.controls}`}
      data-compact={compact || undefined}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault()
        close()
      }}
    >
      <header>
        <h2>{title}</h2>
        <button type="button" onClick={close} aria-label={`关闭${title}`}>
          关闭
        </button>
      </header>
      <div className={css.dialogBody}>{children}</div>
    </dialog>
  )
}
