import { useState } from 'react'
import { holdingCost, money } from '../business-model.js'
import { useInvestment } from '../investment/useInvestment.js'
import css from './Account.module.css'
import type { Actions } from './types.js'
export function Account({ select }: Pick<Actions, 'select'>) {
  const { facts, error } = useInvestment()
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem('huohuo.hide-account') === 'true'
    } catch {
      return false
    }
  })
  const amount = (value: number | null) => (hidden ? '••••' : money(value))
  return (
    <section className={css.account} aria-label="我的账户">
      <div className={css.accountTitle}>
        <strong>我的账户</strong>
        <button
          aria-pressed={hidden}
          onClick={() => {
            setHidden(!hidden)
            try {
              localStorage.setItem('huohuo.hide-account', String(!hidden))
            } catch {}
          }}
        >
          {hidden ? '显示金额' : '隐藏金额'}
        </button>
        <small>
          {error
            ? '账户读取失败'
            : !facts
              ? '正在读取账户…'
              : !facts.updated_at
                ? '尚未录入投资记录'
                : ''}
        </small>
      </div>
      <div className={css.accountMetric}>
        <small title="行情尚未接入，暂不能计算市值">持仓市值 / 元</small>
        <b>{amount(null)}</b>
      </div>
      <div className={css.accountMetric}>
        <small title="缺少日收益基准，暂不能计算盈亏">今日盈亏 / 元</small>
        <b>{amount(null)}</b>
      </div>
      <div className={css.accountMetric}>
        <small title="已记录持仓成本，不含现金；未录入成本时保持未知">持仓成本 / 元</small>
        <b>{amount(holdingCost(facts))}</b>
      </div>
      <small className={css.note}>
        行情未接入 · 日收益基准缺失
        {facts?.holdings.some((p: any) => p.cost_price == null) ? ' · 成本待补全' : ''}
      </small>
      <div className={css.accountLink}>
        <button onClick={() => select('huohuo-investment')}>
          {facts && facts.holdings_status !== 'not_recorded' ? facts.holdings.length : '—'} 只持仓 ·{' '}
          {facts && facts.watchlist_status !== 'not_recorded' ? facts.watchlist.length : '—'} 只自选
          →
        </button>
      </div>
    </section>
  )
}
