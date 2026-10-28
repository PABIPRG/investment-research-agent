import business from '../Business.module.css'
import css from '../Investment.module.css'
import { holdingCost, money, recordedName, securityName } from '../business-model.js'
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
export function HoldingsTable({
  facts,
  query,
  edit,
  mandates = [],
  relationError = false,
  relationLoading = false,
  visit,
}: {
  facts: Facts
  query: string
  edit: (target: EditTarget) => void
  mandates?: MandateView[]
  relationError?: boolean
  relationLoading?: boolean
  visit?: (mandate: string) => void
}) {
  const search = (x: { ticker: string; name?: string; display_name?: string | null }) =>
    `${x.ticker} ${x.display_name || x.name || ''}`.includes(query.trim())
  const holdings = facts.holdings.filter(search),
    watchlist = facts.watchlist.filter(search),
    trades = facts.trades.filter((t) => search({ ...t, name: recordedName(facts, t.ticker) }))
  const begin = (kind: 'holding' | 'trade' | 'revision', position?: Position, trade?: Trade) =>
    edit({ kind, position, trade })
  return (
    <section aria-label="持仓明细">
      <div className={business.metrics}>
        <span>
          持仓成本 <b>{money(holdingCost(facts))}</b>
        </span>
        <span>
          持仓浮盈 <b>—</b>
        </span>
        <span>
          已关联委托{' '}
          <b>
            {relationLoading
              ? '更新中'
              : relationError
                ? '—'
                : `${holdings.filter((p) => mandates.some((m) => m.revision.scope.entity_id.endsWith(':' + p.ticker))).length} / ${holdings.length}`}
          </b>
        </span>
        <small>不含现金 · 行情与收益数据尚未接入</small>
      </div>
      <div className={business.tableWrap}>
        <table className={business.table}>
          <thead>
            <tr>
              {[
                '证券',
                '数量 / 成本',
                '现价 / 涨跌',
                '市值 / 占比',
                '浮盈 / 收益率',
                '来源 / 确认时间',
                '研究关联',
                '操作',
              ].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!holdings.length && (
              <tr>
                <td colSpan={8} className={business.empty}>
                  {query
                    ? '没有匹配的持仓，可清除搜索。'
                    : facts.holdings_status === 'not_recorded'
                      ? '持仓尚未录入，不能据此判断空仓。'
                      : '已记录的持仓为空。'}
                </td>
              </tr>
            )}
            {holdings.map((p) => (
              <tr key={p.ticker}>
                <td>
                  <strong
                    title={
                      p.name_source === 'security_directory'
                        ? '证券目录补充的展示名称；原始投资记录保持不变'
                        : undefined
                    }
                  >
                    {securityName(p.ticker, p.display_name, p.name)}
                  </strong>
                  <small>{p.ticker}</small>
                </td>
                <td>
                  {fmt(p.quantity)} {quantityUnit(p)}
                  <small>
                    {money(p.cost_price)} 元/{quantityUnit(p)}
                  </small>
                </td>
                <td>
                  —<small>暂无行情</small>
                </td>
                <td>
                  —<small>—</small>
                </td>
                <td>
                  —<small>—</small>
                </td>
                <td>
                  用户记录<small>{date(p.position_time)}</small>
                </td>
                <td>
                  {relationLoading
                    ? '正在更新关联…'
                    : relationError
                      ? '关联暂未读取'
                      : mandates.filter((m) => m.revision.scope.entity_id.endsWith(':' + p.ticker))
                            .length
                        ? mandates
                            .filter((m) => m.revision.scope.entity_id.endsWith(':' + p.ticker))
                            .map((m, i) => (
                              <button
                                title={m.revision.goal}
                                key={m.mandate.mandate_id}
                                onClick={() => visit?.(m.mandate.mandate_id)}
                              >
                                查看委托{i ? ` ${i + 1}` : ''}
                              </button>
                            ))
                        : '未设委托'}
                </td>
                <td>
                  <button disabled={false} onClick={() => begin('holding', p)}>
                    校正
                  </button>
                  <button disabled={false} onClick={() => begin('trade', p)}>
                    录入成交
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={css.note}>资料校正不记作成交。行情缺失显示“—”，成本金额不等于市值或收益。</p>
    </section>
  )
}
