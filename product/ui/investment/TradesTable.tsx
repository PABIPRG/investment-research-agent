import business from '../Business.module.css'
import css from '../Investment.module.css'
import { money, recordedName } from '../business-model.js'
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
export function TradesTable({
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
    edit({
      kind,
      position,
      trade,
      securityName: trade ? recordedName(facts, trade.ticker) : undefined,
    })
  return (
    <section aria-label="操作记录">
      <p className={css.note}>
        实际发生时间与录入时间分别保留；这里只记录已发生的操作，不向券商下单。
      </p>
      <div className={business.tableWrap}>
        <table className={business.table}>
          <thead>
            <tr>
              {['证券', '操作', '数量 / 价格', '发生 / 录入时间', '影响', '修订', '操作'].map(
                (label) => (
                  <th key={label}>{label}</th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {!trades.length && (
              <tr>
                <td colSpan={7} className={business.empty}>
                  {query ? '没有匹配的成交记录。' : '尚无已记录成交。持仓校正记录在“修订历史”中。'}
                </td>
              </tr>
            )}
            {[...trades].reverse().map((t) => (
              <tr key={t.request_id}>
                <td>
                  <strong>{recordedName(facts, t.ticker)}</strong>
                  <small>{t.ticker}</small>
                </td>
                <td>{t.voided ? '已撤销' : t.side === 'buy' ? '买入' : '卖出'}</td>
                <td>
                  {fmt(t.quantity)} {quantityUnit(t)}
                  <small>
                    {money(t.price)} 元 · 费用 {money(t.fees)} 元
                  </small>
                </td>
                <td>
                  {date(t.traded_at)}
                  <small>录入 {date(t.recorded_at)}</small>
                </td>
                <td>{t.affects_holdings ? '计入持仓' : '只补记录'}</td>
                <td>{t.revision_no || 0} 次</td>
                <td>
                  <button disabled={t.voided} onClick={() => begin('revision', undefined, t)}>
                    查看与更正
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
