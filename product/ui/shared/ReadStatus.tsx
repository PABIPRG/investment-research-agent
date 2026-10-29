import css from './Page.module.css'
/** Background refresh announces progress without inserting a new layout row. */
export function ReadStatus({
  loading,
  hasData,
  label = '正在读取…',
}: {
  loading: boolean
  hasData: boolean
  label?: string
}) {
  if (!loading) return null
  return (
    <p role="status" className={hasData ? css.srOnly : undefined}>
      {hasData ? '正在刷新，保留上次读取的内容。' : label}
    </p>
  )
}
