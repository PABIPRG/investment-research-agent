import type { ComponentProps } from 'react'
import css from './Controls.module.css'

/** Keep native selection, keyboard and form semantics; theme the closed control. */
export function Select(props: ComponentProps<'select'>) {
  return (
    <span className={css.select}>
      <select {...props} />
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </span>
  )
}
