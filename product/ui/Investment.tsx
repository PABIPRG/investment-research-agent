import controls from './shared/Controls.module.css'
import { ReadStatus } from './shared/ReadStatus.js'
import page from './shared/Page.module.css'
import { useEffect, useRef, useState } from 'react'
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
import { RiskPreference } from './investment/RiskPreference.js'
import { PersonalizationPage } from './personalization/PersonalizationPage.js'
import { PositionRiskPlans } from './investment/PositionRiskPlans.js'
const tabs = {
  holdings: '持仓',
  watchlist: '自选',
  trades: '操作记录',
  history: '修订历史',
  risk: '风险偏好',
  personal: '为我关注',
  protection: '持仓风险',
}
export function InvestmentPage({ visit }: { visit?: (mandate: string) => void }) {
  const root = useRef<HTMLElement>(null)
  const [viewRefresh, setViewRefresh] = useState(0)
  const { facts, loading, error, refresh } = useInvestment()
  const [tab, setTab] = useState<keyof typeof tabs>('holdings'),
    [query, setQuery] = useState(''),
    [edit, setEdit] = useState<EditTarget>(),
    [notice, setNotice] = useState('')
  useEffect(() => {
    root.current?.scrollTo({ top: 0 })
  }, [tab])
  const [mandates, setMandates] = useState<MandateView[]>([]),
    [relationLoading, setRelationLoading] = useState(false),
    [relationError, setRelationError] = useState(false),
    [relationRefresh, setRelationRefresh] = useState(0)
  useEffect(() => {
    const abort = new AbortController()
    setRelationLoading(true)
    void request<{ items: MandateView[] }>('mandates', undefined, abort.signal)
      .then((data) => {
        if (!abort.signal.aborted) {
          setMandates(data.items)
          setRelationError(false)
          setRelationLoading(false)
        }
      })
      .catch(() => {
        if (!abort.signal.aborted) {
          setRelationError(true)
          setRelationLoading(false)
        }
      })
    return () => abort.abort()
  }, [relationRefresh, facts?.version])
  const reload = () => {
    refresh()
    setViewRefresh((n) => n + 1)
    setRelationRefresh((n) => n + 1)
  }
  const common = facts ? { facts, query, edit: setEdit } : undefined
  const open = () => {
    setNotice('')
    setEdit({ kind: tab === 'watchlist' ? 'watchlist' : tab === 'trades' ? 'trade' : 'holding' })
  }
  return (
    <main
      ref={root}
      className={`${page.surface} ${business.page} ${css.page} ${controls.controls}`}
    >
      <header className={`${page.header} ${business.header}`}>
        <div>
          <h1>持仓与自选</h1>
          <p className={business.note}>
            {tab === 'personal'
              ? '资讯、研究兴趣与学习偏好'
              : tab === 'protection'
                ? '持仓目标、组合风险与提醒依据'
                : facts
                  ? facts.updated_at
                    ? `${date(facts.updated_at)} 更新 · 本地记录 v${facts.version}`
                    : '尚无本地投资记录'
                  : '正在读取投资记录'}{' '}
            {['holdings', 'trades'].includes(tab) && '· 金额单位：元'}
          </p>
        </div>
        <div className={business.tools}>
          <button disabled={loading} onClick={reload}>
            刷新
          </button>
          {!['history', 'risk', 'personal', 'protection'].includes(tab) && (
            <button data-variant="primary" disabled={!facts || loading} onClick={open}>
              {tab === 'watchlist' ? '添加自选' : tab === 'trades' ? '记录成交' : '添加持仓'}
            </button>
          )}
        </div>
      </header>
      <ReadStatus loading={loading} hasData={facts !== undefined} />
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
      <div className={css.tabNav} aria-label="投资记录分类">
        {Object.entries(tabs).map(([key, label]) => (
          <button
            key={key}
            aria-pressed={key === tab}
            onClick={() => {
              setTab(key as keyof typeof tabs)
              setQuery('')
              setNotice('')
            }}
          >
            {label}
            {facts && (key === 'holdings' || key === 'watchlist') ? ` ${facts[key].length}` : ''}
          </button>
        ))}
      </div>
      {!['history', 'risk', 'personal', 'protection'].includes(tab) && (
        <div className={css.filters}>
          <label>
            搜索证券
            <input
              aria-label="搜索证券"
              value={query}
              placeholder="名称或代码"
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && <button onClick={() => setQuery('')}>清除</button>}
          </label>
        </div>
      )}
      {common && tab === 'holdings' && (
        <HoldingsTable
          {...common}
          mandates={mandates}
          relationError={relationError}
          relationLoading={relationLoading}
          visit={visit}
        />
      )}{' '}
      {common && tab === 'watchlist' && <WatchlistTable {...common} />}{' '}
      {common && tab === 'trades' && <TradesTable {...common} />}{' '}
      {common && tab === 'history' && <RevisionHistory {...common} />}
      {facts && tab === 'risk' && <RiskPreference facts={facts} />}
      {tab === 'personal' && (
        <PersonalizationPage
          refreshKey={viewRefresh}
          hasSecurities={!!facts && facts.holdings.length + facts.watchlist.length > 0}
        />
      )}
      {facts && tab === 'protection' && (
        <PositionRiskPlans facts={facts} visit={visit} refreshKey={viewRefresh} />
      )}
      {edit && (
        <InvestmentEditor
          target={edit}
          close={() => setEdit(undefined)}
          saved={(version) => {
            setEdit(undefined)
            const place =
              edit?.kind === 'watchlist' || edit?.kind === 'remove'
                ? '自选'
                : edit?.kind === 'trade'
                  ? '操作记录'
                  : '修订历史'
            setNotice(`已保存为记录 v${version}，可在${place}回查。`)
          }}
        />
      )}
    </main>
  )
}
