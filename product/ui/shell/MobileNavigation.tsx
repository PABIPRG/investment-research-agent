import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Navigation } from './Navigation.js'
import type { Actions } from './types.js'
import css from './MobileNavigation.module.css'

export function MobileNavigation({
  open,
  show,
  close,
  panel,
  select,
  quiet,
  toggle,
  settings,
}: {
  open: boolean
  show: () => void
  close: () => void
  panel: string | null
  select: Actions['select']
  quiet: boolean
  toggle: () => void
  settings: ReactNode
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const id = useId()
  const dismiss = () => {
    dialog.current?.close()
    close()
  }
  useEffect(() => {
    const node = dialog.current!
    if (open && !node.open) node.showModal()
    if (!open && node.open) node.close()
  }, [open])
  useEffect(() => () => dialog.current?.close(), [])
  return (
    <>
      <button
        className={css.trigger}
        aria-label="打开菜单"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={id}
        onClick={show}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <dialog
        ref={dialog}
        id={id}
        className={css.drawer}
        data-huohuo-menu
        aria-labelledby={`${id}-title`}
        onCancel={(e) => {
          e.preventDefault()
          dismiss()
        }}
        onKeyDown={(e) => {
          if (!e.currentTarget.open) return
          if (e.key === ',' && e.altKey && (e.metaKey || e.ctrlKey)) dismiss()
          if (e.key === 'Tab') {
            const stops = Array.from(
              e.currentTarget.querySelectorAll<HTMLElement>(
                'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])',
              ),
            ).filter((node) => node.getClientRects().length > 0)
            const first = stops[0],
              last = stops.at(-1)
            if (
              (e.shiftKey && document.activeElement === first) ||
              (!e.shiftKey && document.activeElement === last)
            ) {
              e.preventDefault()
              ;(e.shiftKey ? last : first)?.focus()
            }
          }
        }}
        onClick={(e) => {
          if (e.target !== e.currentTarget) return
          const r = e.currentTarget.getBoundingClientRect()
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            dismiss()
        }}
      >
        <header className={css.head}>
          <h2 id={`${id}-title`}>菜单</h2>
          <button className={css.close} aria-label="关闭菜单" onClick={dismiss} autoFocus>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m6 6 12 12M6 18 18 6" />
            </svg>
          </button>
        </header>
        <Navigation
          panel={panel}
          variant="drawer"
          className={css.navigation}
          select={(id) => {
            dismiss()
            select(id)
          }}
        />
        <footer className={css.footer}>
          <button className={css.presence} onClick={toggle} aria-pressed={quiet}>
            {quiet ? '显示对话火火' : '隐藏对话火火'}
          </button>
          <div
            className={css.settings}
            onClickCapture={(e) => {
              // Close the native dialog before the existing settings launcher opens its body portal.
              if (
                e.currentTarget.contains(e.target as Node) &&
                (e.target as Element).closest('button[aria-haspopup="dialog"]')
              )
                dismiss()
            }}
          >
            {settings}
          </div>
        </footer>
      </dialog>
    </>
  )
}
