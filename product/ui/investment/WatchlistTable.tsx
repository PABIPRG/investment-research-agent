import business from '../Business.module.css'
import { recordedName, securityName } from '../business-model.js'
import type { MandateView } from '../mandates/model.js'
import { date, type EditTarget, type Facts, type Position, type Trade } from './types.js'
export function WatchlistTable({
  facts,
  query,
  edit,
  mandates = [],
  relationError = false,
  visit,
}: {
  facts: Facts
  query: string
  edit: (target: EditTarget) => void
  mandates?: MandateView[]
  relationError?: boolean
  visit?: (mandate: string) => void
}) {
  const search = (x: { ticker: string; name?: string }) =>
    `${x.ticker} ${x.name || ''}`.includes(query.trim())
  const holdings = facts.holdings.filter(search),
    watchlist = facts.watchlist.filter(search),
    trades = facts.trades.filter((t) => search({ ...t, name: recordedName(facts, t.ticker) }))
  const begin = (kind: 'holding' | 'trade' | 'revision', position?: Position, trade?: Trade) =>
    edit({ kind, position, trade })
  return (
    <section aria-label="自选明细">
      <div className={business.tableWrap}>
        <table className={business.table}>
          <thead>
            <tr>
              {['证券', '关注原因', '加入时间', '操作'].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!watchlist.length && (
              <tr>
                <td colSpan={4} className={business.empty}>
                  {query ? '没有匹配的自选，可清除搜索。' : '暂无自选，加入自选不会创建持续委托。'}
                </td>
              </tr>
            )}
            {watchlist.map((p) => (
              <tr key={p.ticker}>
                <td>
                  <strong>{securityName(p.ticker, p.name)}</strong>
                  <small>{p.ticker}</small>
                </td>
                <td>{p.reason || '未填写关注原因'}</td>
                <td>{date(p.added_at)}</td>
                <td>
                  <button
                    disabled={false}
                    onClick={() => {
                      edit({ kind: 'remove', watch: p })
                    }}
                  >
                    移除自选
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
