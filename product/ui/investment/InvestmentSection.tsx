import type { ReactNode } from 'react'
import css from './Sections.module.css'
export function InvestmentSection({
  title,
  hint,
  actions,
  children,
}: {
  title: string
  hint?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={css.section} aria-label={title}>
      <header className={css.heading}>
        <div>
          <h3>{title}</h3>
          {hint && <p>{hint}</p>}
        </div>
        {actions && <div className={css.actions}>{actions}</div>}
      </header>
      <div className={css.content}>{children}</div>
    </section>
  )
}
