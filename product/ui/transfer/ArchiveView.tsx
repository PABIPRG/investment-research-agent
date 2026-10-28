import { useEffect, useState } from 'react'
import { labels, failure, type Category, type TransferRequest } from './model.js'
import css from './Transfer.module.css'
export function ArchiveView({ api }: { api: TransferRequest }) {
  const [data, setData] = useState<any>(),
    [detail, setDetail] = useState<any>(),
    [offset, setOffset] = useState(0),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let live = true
    setBusy(true)
    setError('')
    api({ operation: 'archive', offset, limit: 20 })
      .then((x) => {
        if (live) setData(x)
      })
      .catch((e) => {
        if (live) setError(failure(e))
      })
      .finally(() => {
        if (live) setBusy(false)
      })
    return () => {
      live = false
    }
  }, [offset, refresh])
  async function open(id: string) {
    setBusy(true)
    setError('')
    try {
      setDetail(await api({ operation: 'archive', archive_id: id }))
    } catch (e) {
      setError(failure(e))
    } finally {
      setBusy(false)
    }
  }
  const document = detail?.document
  const content =
    typeof document === 'string'
      ? document
      : (document?.content ?? document?.summary ?? document?.text ?? document?.markdown)
  return (
    <section aria-label="旧资料档案">
      <div className={css.actions}>
        <h3>旧资料档案</h3>
        <button disabled={busy} onClick={() => setRefresh((v) => v + 1)}>
          刷新档案
        </button>
      </div>
      <p className={css.note}>仅供回看，不是当前 DSH 会话或新研究证据。</p>
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">正在读取旧资料…</p>}
      {detail ? (
        <article className={css.change}>
          <button onClick={() => setDetail(undefined)}>返回档案列表</button>
          <h3>{detail.title}</h3>
          <p className={css.note}>
            {labels[detail.category as Category]} · 导入于{' '}
            {new Date(detail.imported_at).toLocaleString()}
          </p>
          {typeof content === 'string' && <div className={css.archiveText}>{content}</div>}
          <details open={typeof content !== 'string'}>
            <summary>查看保留的原始记录</summary>
            <pre className={css.archiveText}>{JSON.stringify(document, null, 2)}</pre>
          </details>
        </article>
      ) : (
        <>
          <ul className={css.archives}>
            {data?.items.map((item: any) => (
              <li key={item.id}>
                <button disabled={busy} onClick={() => void open(item.id)}>
                  {item.title}
                </button>
                <small>{labels[item.category as Category]}</small>
              </li>
            ))}
          </ul>
          {data?.total === 0 && <p>还没有旧资料。选择并导入旧数据后会保存在这里。</p>}
          {data?.total > 20 && (
            <div className={css.actions}>
              <button
                disabled={busy || offset === 0}
                onClick={() => setOffset((v) => Math.max(0, v - 20))}
              >
                上一页
              </button>
              <span>
                {offset + 1}–{Math.min(offset + 20, data.total)} / {data.total}
              </span>
              <button
                disabled={busy || offset + 20 >= data.total}
                onClick={() => setOffset((v) => v + 20)}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
