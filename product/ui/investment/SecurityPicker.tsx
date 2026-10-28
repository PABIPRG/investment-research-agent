import { useEffect, useId, useRef, useState } from 'react'
import css from '../Form.module.css'
import { errorText, request } from '../shared/api.js'
import { searchMessage, selectableSecurities, type SearchResult } from './search-model.js'
import type { Security } from './types.js'
import { ManualSecurity } from './ManualSecurity.js'
export function SecurityPicker({
  value,
  onChange,
  locked = false,
  disabled = false,
}: {
  value?: Security
  onChange: (value?: Security) => void
  locked?: boolean
  disabled?: boolean
}) {
  const [query, setQuery] = useState(value?.name || ''),
    [revision, setRevision] = useState(0),
    [open, setOpen] = useState(false)
  const [rows, setRows] = useState<Security[]>([]),
    [loading, setLoading] = useState(false),
    [message, setMessage] = useState('')
  const [active, setActive] = useState(-1)
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!open || !query.trim() || value || locked) return
    const abort = new AbortController()
    setRows([])
    setLoading(true)
    setMessage('')
    setActive(-1)
    const timer = setTimeout(() => {
      void request<SearchResult>('security-search', { query: query.trim() }, abort.signal)
        .then((data) => {
          if (!abort.signal.aborted) {
            setRows(selectableSecurities(data))
            setMessage(searchMessage(data))
          }
        })
        .catch((e) => {
          if (!abort.signal.aborted) setMessage(errorText(e))
        })
        .finally(() => {
          if (!abort.signal.aborted) setLoading(false)
        })
    }, 250)
    return () => {
      abort.abort()
      clearTimeout(timer)
    }
  }, [query, revision, open, value, locked])
  const select = (item: Security) => {
    onChange(item)
    setQuery(item.name)
    setActive(-1)
    setOpen(false)
    input.current?.focus()
  }
  if (locked && value)
    return (
      <div className={css.security}>
        <small>本次记录的证券</small>
        <strong>{value.name}</strong>
        <span>{value.code} · 此次记录保留原证券</span>
      </div>
    )
  return (
    <div
      className={css.picker}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false)
      }}
    >
      <label htmlFor={id}>证券名称或代码</label>
      <input
        id={id}
        ref={input}
        role="combobox"
        aria-expanded={open && !value}
        aria-controls={`${id}-results`}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-${active}` : undefined}
        autoComplete="off"
        disabled={disabled}
        maxLength={100}
        value={query}
        placeholder="搜索并选择沪深 A 股"
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value)
          onChange(undefined)
          setRows([])
          setMessage('')
          setOpen(true)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && open) {
            e.preventDefault()
            e.stopPropagation()
            setOpen(false)
          }
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((i) => Math.min(i + 1, rows.length - 1))
          }
          if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((i) => Math.max(i - 1, 0))
          }
          if (e.key === 'Enter' && open && !value) {
            e.preventDefault()
            if (rows[active]) select(rows[active])
          }
        }}
      />
      {value ? (
        <div className={css.selected}>
          <strong>{value.name}</strong>
          <span>
            {value.code} · {value.market || value.exchange || '已选择'}
          </span>
        </div>
      ) : (
        <small>选中匹配结果后再继续；仅查询不会添加持仓或委托。</small>
      )}
      {open && !value && query.trim() && (
        <div className={css.results}>
          {loading && <p role="status">正在搜索…</p>}
          {message && (
            <p role="status">
              {message}{' '}
              <button type="button" onClick={() => setRevision((n) => n + 1)}>
                重试
              </button>
            </p>
          )}
          <ul id={`${id}-results`} role="listbox" aria-label="证券搜索结果">
            {rows.map((row, i) => (
              <li key={row.code} id={`${id}-${i}`} role="option" aria-selected={i === active}>
                <button type="button" onClick={() => select(row)}>
                  <strong>{row.name}</strong>
                  <span>
                    {row.code} · {row.market || row.exchange}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {!value && <ManualSecurity select={select} disabled={disabled} />}
    </div>
  )
}
