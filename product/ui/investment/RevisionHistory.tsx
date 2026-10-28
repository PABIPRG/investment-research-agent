import business from '../Business.module.css'
import { TradeRevisionValues } from './TradeRevisionValues.js'
import { money, recordedName, securityName } from '../business-model.js'
import type { MandateView } from '../mandates/model.js'
import {
  quantityUnit,
  date,
  fmt,
  type EditTarget,
  type Facts,
  type Position,
  type Trade,
} from './types.js'
export function RevisionHistory({
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
    <section aria-label="修订历史">
      <div className={business.tableWrap}>
        <table className={business.table}>
          <thead>
            <tr>
              {['对象', '变更', '前后值', '原因 / 来源'].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!facts.corrections.length && !facts.revisions.length && (
              <tr>
                <td colSpan={4} className={business.empty}>
                  尚无校正或修订记录。
                </td>
              </tr>
            )}
            {[...facts.corrections].reverse().map((x, i) => (
              <tr key={'c' + i}>
                <td>
                  <strong>{securityName(x.ticker, x.name)}</strong>
                  <small>{x.ticker}</small>
                </td>
                <td>
                  持仓校正<small>{date(x.recorded_at)}</small>
                </td>
                <td>
                  {fmt(x.before?.quantity ?? 0)} → {fmt(x.after?.quantity ?? 0)}{' '}
                  {quantityUnit(x.after || x.before || x)}
                  <small>
                    成本 {money(x.before?.cost_price)} → {money(x.after?.cost_price)}
                  </small>
                </td>
                <td>
                  {x.reason}
                  <small>用户记录</small>
                </td>
              </tr>
            ))}
            {[...facts.revisions].reverse().map((x, i) => (
              <tr key={'r' + i}>
                <td>
                  {recordedName(facts, x.previous?.ticker || '')}
                  <small>{x.previous?.ticker}</small>
                </td>
                <td>
                  成交修订 {x.revision_no}
                  <small>{date(x.revised_at)}</small>
                </td>
                <td>
                  <details>
                    <summary>核对原记录与修订值</summary>
                    <TradeRevisionValues before={x.previous} after={x.amended} />
                  </details>
                </td>
                <td>{x.reason || '未填写原因'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
