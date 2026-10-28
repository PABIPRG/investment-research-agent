import controls from '../shared/Controls.module.css'
import { Select } from '../shared/Select.js'
import { useEffect, useState } from 'react'
import { CapabilityRow } from './CapabilityRow.js'
import {
  filterCapabilities,
  statusLabels,
  type Capability,
  type CapabilityCatalog,
  type CapabilityStatus,
} from './model.js'
import css from './Capabilities.module.css'
export function CapabilitiesSection({
  close,
  select,
  start,
}: {
  close: () => void
  select: (id: string) => void
  start: (prompt: string) => void
}) {
  const [data, setData] = useState<CapabilityCatalog>(),
    [error, setError] = useState(false)
  const [loading, setLoading] = useState(true),
    [version, setVersion] = useState(0)
  const [query, setQuery] = useState(''),
    [kind, setKind] = useState<'all' | Capability['kind']>('all')
  const [status, setStatus] = useState<'all' | CapabilityStatus>('all')
  useEffect(() => {
    const abort = new AbortController()
    setLoading(true)
    setError(false)
    fetch('api/huohuo/capabilities', { cache: 'no-store', signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error()
        const next = (await r.json()) as CapabilityCatalog
        if (next.scope !== 'product-preset' || !Array.isArray(next.items)) throw Error()
        if (!abort.signal.aborted) setData(next)
      })
      .catch(() => {
        if (!abort.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false)
      })
    return () => abort.abort()
  }, [version])
  const items = filterCapabilities(data?.items ?? [], query, kind, status)
  const reset = () => {
    setQuery('')
    setKind('all')
    setStatus('all')
  }
  return (
    <section className={`${css.root} ${controls.controls}`} aria-label="工具与 Skill">
      <header className={css.header}>
        <div>
          <h2>工具与 Skill</h2>
          <p>查看本版本火火的能力、用途与接入限制。</p>
        </div>
        <button disabled={loading} onClick={() => setVersion((v) => v + 1)}>
          {loading ? '读取中…' : '刷新目录'}
        </button>
      </header>
      <div className={css.filters}>
        <label className={css.search}>
          搜索工具与 Skill
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="名称、用途或内部名称"
            type="search"
          />
        </label>
        <div className={css.types} role="group" aria-label="能力类型">
          {(['all', 'tool', 'skill'] as const).map((value) => (
            <button key={value} aria-pressed={kind === value} onClick={() => setKind(value)}>
              {value === 'all' ? '全部' : value === 'tool' ? 'Tool' : 'Skill'}
            </button>
          ))}
        </div>
        <label className={css.state}>
          状态
          <Select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            <option value="all">全部状态</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </label>
      </div>
      {error && (
        <div className={css.feedback} role="alert">
          {data
            ? '刷新失败，当前显示上次读取的目录。'
            : '暂时无法读取能力目录。请点击“刷新目录”重试。'}
        </div>
      )}
      {data && (
        <>
          <p className={css.caption} role="status">
            显示 {items.length} / {data.items.length} 项 · 已注册不代表资料源始终可用
          </p>
          {items.length ? (
            <div className={css.list}>
              {items.map((item) => (
                <CapabilityRow
                  key={`${item.kind}:${item.id}`}
                  item={item}
                  start={(prompt) => {
                    close()
                    start(prompt)
                  }}
                  strategy={() => {
                    close()
                    select('huohuo-evolution')
                  }}
                  investment={() => {
                    close()
                    select('huohuo-investment')
                  }}
                />
              ))}
            </div>
          ) : (
            <div className={css.empty}>
              <p>{data.items.length ? '没有匹配的能力。' : '当前版本没有可展示的产品能力。'}</p>
              {!!data.items.length && <button onClick={reset}>清除筛选</button>}
            </div>
          )}
          <p className={css.footer}>
            当前为产品装配目录，不会执行工具或改变权限。
            <br />
            聊天和页面共用投资记录；新增、更正及偏好修改均需核对并确认，密钥在安全表单填写。
          </p>
        </>
      )}
      {!data && loading && (
        <p className={css.empty} role="status">
          正在读取本实例的工具与 Skill…
        </p>
      )}
    </section>
  )
}
