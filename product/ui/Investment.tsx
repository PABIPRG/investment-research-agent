import page from './shared/Page.module.css'
import { useEffect, useState } from 'react'
import business from './Business.module.css'
import css from './Investment.module.css'
import { HoldingsTable } from './investment/HoldingsTable.js'
import { InvestmentEditor } from './investment/InvestmentEditor.js'
import { RevisionHistory } from './investment/RevisionHistory.js'
import { TradesTable } from './investment/TradesTable.js'
import { date, type EditTarget } from './investment/types.js'
import { useInvestment } from './investment/useInvestment.js'
import { WatchlistTable } from './investment/WatchlistTable.js'
import type { MandateView } from './mandates/model.js'
import { request } from './shared/api.js'
const tabs = { holdings: '持仓', watchlist: '自选', trades: '操作记录', history: '修订历史' }
export function InvestmentPage({ visit }: { visit?: (mandate: string) => void }) {
  const { facts, loading, error, refresh } = useInvestment()
  const [tab, setTab] = useState<keyof typeof tabs>('holdings'),
    [query, setQuery] = useState(''),
    [edit, setEdit] = useState<EditTarget>(),
    [notice, setNotice] = useState('')
  const [mandates, setMandates] = useState<MandateView[]>([]),
    [relationError, setRelationError] = useState(false),
    [relationRefresh, setRelationRefresh] = useState(0)
  useEffect(() => {
    const abort = new AbortController()
    void request<{ items: MandateView[] }>('mandates', undefined, abort.signal)
      .then((data) => {
        if (!abort.signal.aborted) {
          setMandates(data.items)
          setRelationError(false)
        }
      })
      .catch(() => {
        if (!abort.signal.aborted) setRelationError(true)
      })
    return () => abort.abort()
  }, [relationRefresh])
  const reload = () => {
    refresh()
    setRelationRefresh((n) => n + 1)
  }
  const common = facts ? { facts, query, edit: setEdit } : undefined
  const open = () => {
    setNotice('')
    setEdit({ kind: tab === 'watchlist' ? 'watchlist' : tab === 'trades' ? 'trade' : 'holding' })
  }
  return (
    <main className={`${page.surface} ${business.page} ${css.page}`}>
      <header className={`${page.header} ${business.header}`}>
        <div>
          <h1>持仓与自选</h1>
          <p className={business.note}>
            {facts ? `${date(facts.updated_at)} 更新 · 记录 v${facts.version}` : '正在读取投资记录'}{' '}
            · 金额单位：元
          </p>
        </div>
        <div className={business.tools}>
          <button disabled={loading} onClick={reload}>
            刷新
          </button>
          {tab !== 'history' && (
            <button data-variant="primary" disabled={!facts || loading} onClick={open}>
              {tab === 'watchlist' ? '添加自选' : tab === 'trades' ? '记录成交' : '添加持仓'}
            </button>
          )}
        </div>
      </header>
      {loading && <p role="status">{facts ? '正在刷新，保留上次记录…' : '正在读取…'}</p>}
      {error && (
        <p role="alert">
          {error} {facts ? '当前内容可能过期。' : ''}
          <button onClick={reload}>重试</button>
        </p>
      )}
      {notice && (
        <p role="status" className={css.success}>
          {notice}
        </p>
      )}
      <div className={business.tabs} aria-label="投资记录分类">
        {Object.entries(tabs).map(([key, label]) => (
          <button
            key={key}
            aria-pressed={key === tab}
            onClick={() => {
              setTab(key as keyof typeof tabs)
              setQuery('')
            }}
          >
            {label}
            {facts && (key === 'holdings' || key === 'watchlist') ? ` ${facts[key].length}` : ''}
          </button>
        ))}
        {tab !== 'history' && (
          <label className={css.search}>
            搜索证券
            <input
              aria-label="搜索证券"
              value={query}
              placeholder="名称或代码"
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && <button onClick={() => setQuery('')}>清除</button>}
          </label>
        )}
      </div>
      {common && tab === 'holdings' && (
        <HoldingsTable
          {...common}
          mandates={mandates}
          relationError={relationError}
          visit={visit}
        />
      )}{' '}
      {common && tab === 'watchlist' && <WatchlistTable {...common} />}{' '}
      {common && tab === 'trades' && <TradesTable {...common} />}{' '}
      {common && tab === 'history' && <RevisionHistory {...common} />}
      {edit && (
        <InvestmentEditor
          target={edit}
          close={() => setEdit(undefined)}
          saved={(version) => {
            setEdit(undefined)
            setNotice(`已保存为记录 v${version}，可在修订历史回查。`)
          }}
        />
      )}
    </main>
  )
}
