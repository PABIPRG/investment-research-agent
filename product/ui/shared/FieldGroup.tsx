import { useId, type ReactNode } from 'react'
import css from '../Form.module.css'

/** One spacing and hierarchy contract for related fields, without nested cards. */
export function FieldGroup({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: ReactNode
}) {
  const id = useId()
  return (
    <section className={css.group} aria-labelledby={id}>
      <header>
        <h3 id={id}>{title}</h3>
        {hint && <p className={css.hint}>{hint}</p>}
      </header>
      <div className={css.fields}>{children}</div>
    </section>
  )
}
