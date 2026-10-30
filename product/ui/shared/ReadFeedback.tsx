import css from './Page.module.css'
/** Reserve one stable line for read failures; do not insert a row on every poll. */
export function ReadFeedback({ error, notice }: { error?: string; notice?: string }) {
  return (
    <div className={css.feedback} role={error ? 'alert' : notice ? 'status' : undefined}>
      {error ? `${error} 当前内容可能过期。` : notice || '\u00a0'}
    </div>
  )
}
