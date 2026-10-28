import controls from '../shared/Controls.module.css'
import { useEffect, useState } from 'react'
import css from '../capabilities/Capabilities.module.css'
import local from './DataSources.module.css'
async function api(body?: unknown) {
  const r = await fetch(body ? 'api/huohuo/data-source-command' : 'api/huohuo/data-sources', {
    method: body ? 'POST' : 'GET',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const value = await r.json()
  if (!r.ok) throw Error(value.detail || value.error || '资料源暂时无法连接')
  return value
}
export function DataSourcesSection() {
  const [state, setState] = useState<any>(),
    [preview, setPreview] = useState<any>()
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [message, setMessage] = useState('')
  const [terms, setTerms] = useState(false),
    [query, setQuery] = useState(''),
    [items, setItems] = useState<any[]>([])
  const refresh = async () => {
    setState(await api())
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message))
  }, [])
  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作未完成')
    } finally {
      setBusy(false)
    }
  }
  const prepare = (action: string) =>
    run(async () => {
      setPreview(
        await api({
          operation: 'prepare',
          action,
          request_key: crypto.randomUUID(),
          payload: ['bootstrap', 'refresh'].includes(action)
            ? { acknowledge_source_terms: terms }
            : {},
        }),
      )
    })
  const commit = () =>
    run(async () => {
      const result = await api({
        operation: 'commit',
        preview_id: preview.preview_id,
        request_key: preview.request_key,
      })
      if (result.status !== 'committed')
        throw Error(result.error || result.message || '操作未完成，请先刷新状态核对')
      setPreview(undefined)
      setMessage('已完成并保存到本实例。')
      await refresh()
    })
  return (
    <section className={`${css.root} ${local.root} ${controls.controls}`} aria-label="资料源">
      <header className={css.header}>
        <div>
          <h2>资料源</h2>
          <p>管理当前实例的产业链资料和证券基础清单。</p>
        </div>
        <button disabled={busy} onClick={() => run(refresh)}>
          刷新状态
        </button>
      </header>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <section className={local.source}>
        <header>
          <h3>产业链图谱</h3>
          <strong>{state ? (state.available ? '已就绪' : '尚未下载') : '读取中…'}</strong>
        </header>
        <p>
          下载后可在对话中查询公司上下游、材料、产品和关系网络。新研报整理的增量经你确认后保存。
        </p>
        {state && (
          <dl>
            <div>
              <dt>最近下载</dt>
              <dd>
                {state.downloaded_at
                  ? new Date(state.downloaded_at * 1000).toLocaleString('zh-CN')
                  : '尚未下载'}
              </dd>
            </div>
            <div>
              <dt>研报增量</dt>
              <dd>
                {state.overlay_companies} 家公司 · {state.inferred_links} 条推断关系
              </dd>
            </div>
            <div>
              <dt>A 股基础清单</dt>
              <dd>{state.universe_companies} 家公司</dd>
            </div>
          </dl>
        )}
        <p className={css.note}>
          来源：IDUXGRAPH / iducsite。关系可能含推断，不能替代原始披露。完整图查询约需 1 GB
          内存；首次下载约 140 MB，程序上限 256 MiB。资料只保存在本实例，不随产品分发。
        </p>
        <label className={local.check}>
          <input
            type="checkbox"
            checked={terms}
            onChange={(e) => setTerms(e.target.checked)}
            disabled={busy}
          />
          我已核对第三方资料使用条件，确认本次用途获准
        </label>
        <div className={local.actions}>
          <button
            disabled={busy || !terms}
            onClick={() => prepare(state?.available ? 'refresh' : 'bootstrap')}
          >
            {state?.available ? '更新产业链资料' : '下载产业链资料'}
          </button>
          <button disabled={busy} onClick={() => prepare('refresh_universe')}>
            更新 A 股基础清单
          </button>
          {state?.available && (
            <button disabled={busy} onClick={() => prepare('delete')}>
              删除本地种子
            </button>
          )}
        </div>
        {preview && (
          <section className={local.preview} aria-label="确认资料源操作">
            <h4>请确认操作范围</h4>
            <p>{preview.summary}</p>
            <div className={local.actions}>
              <button disabled={busy} onClick={commit}>
                {busy ? '正在处理…' : '确认执行'}
              </button>
              <button disabled={busy} onClick={() => setPreview(undefined)}>
                暂不执行
              </button>
            </div>
          </section>
        )}
      </section>
      {state?.basic_available && (
        <section className={local.source}>
          <h3>检查资料覆盖</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              run(async () => {
                const result = await api({
                  operation: 'query',
                  path: '/companies',
                  params: { keyword: query, limit: 12 },
                })
                if (result.status !== 'ok') throw Error(result.error)
                setItems(result.data.items)
              })
            }}
          >
            <label>
              公司名称或代码
              <input value={query} maxLength={100} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <button disabled={busy}>查询覆盖</button>
          </form>
          <ul>
            {items.map((item) => (
              <li key={item.code}>
                {item.name} <small>{item.code}</small>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className={local.source}>
        <h3>行情、技术指标与新闻</h3>
        <p>
          公开资料按需读取，无需配置旧系统地址。在对话中明确证券或市场问题即可使用；持续提醒在「我的委托」确认资料范围、条件和时间。
        </p>
        <p className={css.note}>
          查询会保留来源时间、陈旧与缺失状态。资料失败不会被当作行情没有变化。
        </p>
      </section>
    </section>
  )
}
