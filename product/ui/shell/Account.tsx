import { useState } from 'react'
import { accountAmount, accountNote } from '../investment/account-model.js'
import { useAccount } from '../investment/useAccount.js'
import css from './Account.module.css'
import type { Actions } from './types.js'
export function Account({ select }: Pick<Actions, 'select'>) {
  const { account, error, loading, refreshing, refresh } = useAccount()
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem('huohuo.hide-account') === 'true'
    } catch {
      return false
    }
  })
  const amount = (key: 'market_value' | 'daily_pnl' | 'holding_cost') =>
    accountAmount(account?.[key], hidden, error)
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
        <button onClick={refresh} disabled={loading || refreshing} aria-label="刷新账户行情">
          刷新
        </button>
        <small>
          {error ? '账户读取失败' : account?.holdings_status === 'not_recorded' ? '本地未录入' : ''}
        </small>
      </div>
      <div className={css.accountMetric}>
        <small title={account?.market_value.reason}>持仓市值 / 元</small>
        <b>{amount('market_value')}</b>
      </div>
      <div className={css.accountMetric}>
        <small title={account?.daily_pnl.reason}>今日盈亏 / 元</small>
        <b>{amount('daily_pnl')}</b>
      </div>
      <div className={css.accountMetric}>
        <small title={account?.holding_cost.reason}>持仓成本 / 元</small>
        <b>{amount('holding_cost')}</b>
      </div>
      <small className={css.note} title={account?.scope_note} role={error ? 'alert' : undefined}>
        {accountNote(account, error)}
        {!!account?.sources.length && (
          <span>
            {' '}
            ·{' '}
            {Array.from(
              new Set(
                account.sources.map(
                  (s) =>
                    ({ eastmoney: '东方财富', sina: '新浪' })[s.source as 'eastmoney' | 'sina'] ||
                    s.source,
                ),
              ),
            ).join(' / ')}{' '}
            报价时间{' '}
            {new Date(account.sources.map((s) => s.as_of).sort()[0]).toLocaleString('zh-CN')}
          </span>
        )}
      </small>
      <div className={css.accountLink}>
        <button onClick={() => select('huohuo-investment')}>
          {error || !account ? '—' : account.holdings_count} 只持仓 ·{' '}
          {error || !account ? '—' : account.watchlist_count} 只自选 →
        </button>
      </div>
    </section>
  )
}
