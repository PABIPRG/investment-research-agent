import ui from './Sections.module.css'
import { money } from '../business-model.js'
import { quantityUnit, date, fmt, type Trade } from './types.js'
export function TradeRevisionValues({
  before,
  after,
}: {
  before: Trade
  after: Partial<Trade> | null
}) {
  if (!after) return <p>这笔成交记录已撤销；原记录仍保留在修订历史中。</p>
  const direction = (value?: string) =>
    value === 'buy' ? '买入' : value === 'sell' ? '卖出' : '未提供'
  const rows = [
    ['买卖方向', direction(before.side), direction(after.side)],
    [`数量（${quantityUnit(before)}）`, fmt(before.quantity), fmt(after.quantity)],
    ['成交价格（元）', money(before.price), money(after.price)],
    ['费用（元）', money(before.fees), money(after.fees)],
    ['发生时间', date(before.traded_at), date(after.traded_at)],
  ]
  return (
    <dl className={ui.facts}>
      {rows
        .filter(([, a, b]) => a !== b)
        .map(([name, a, b]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>
              {a} → {b}
            </dd>
          </div>
        ))}
      {rows.every(([, a, b]) => a === b) && <p>上述成交字段没有变化，请核对修订原因。</p>}
    </dl>
  )
}
