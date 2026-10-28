import page from './shared/Page.module.css'
import { useEffect, useState } from 'react'
import { markActivitySeen, refreshActivity, useActivity } from './activity/store.js'
import { mandateName } from './business-model.js'
import css from './Business.module.css'
import { time } from './model.js'
import { channelLabels, decisionText, deliveryLabels } from './notifications/model.js'
export function ActivityPage({ visit }: { visit: (mandate: string, decision: string) => void }) {
  const { items, error: activityError, loading } = useActivity()
  const [mandates, setMandates] = useState<any[]>([]),
    [error, setError] = useState(''),
    [detailsLoading, setDetailsLoading] = useState(true),
    [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    setDetailsLoading(true)
    fetch('api/huohuo/mandates', { signal: abort.signal, cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw Error('相关委托暂时无法读取。')
        return response.json()
      })
      .then((data) => setMandates(data.items))
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message)
      })
      .finally(() => {
        if (!abort.signal.aborted) setDetailsLoading(false)
      })
    return () => abort.abort()
  }, [refresh])
  useEffect(() => {
    if (!loading && !detailsLoading && !activityError && !error) markActivitySeen(items)
  }, [items, loading, detailsLoading, activityError, error])
  const failure = activityError || error
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header}`}>
        <div>
          <h1>动态</h1>
          <p className={css.note}>{items.length} 条已保存联系记录 · 可回到委托核对依据</p>
        </div>
        <button
          onClick={() => {
            void refreshActivity()
            setRefresh((n) => n + 1)
          }}
          disabled={loading || detailsLoading}
        >
          刷新动态
        </button>
      </header>
      {loading && <p role="status">正在读取…</p>}
      {failure && <p role="alert">{failure} 已显示内容可能过期。</p>}
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              {['类型 / 时间', '相关委托', '内容与限制', '操作'].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && !failure && !items.length && (
              <tr>
                <td colSpan={4} className={css.empty}>
                  暂无已保存动态。委托产生联系记录后会显示在这里。
                </td>
              </tr>
            )}
            {items.map((row) => {
              const mandate = mandates.find((m) => m.mandate.mandate_id === row.mandate_id)
              return (
                <tr key={`${row.decision_id}:${row.channel}`}>
                  <td>
                    {channelLabels[row.channel] || '联系记录'}
                    <small>{time(row.created_at ?? row.updated_at)}</small>
                  </td>
                  <td>
                    <strong>{mandate ? mandateName(mandate) : '委托信息暂未读取'}</strong>
                    <small>{mandate?.revision.goal}</small>
                  </td>
                  <td>
                    {decisionText(row.decision_detail || '', row.reason_code || '')}
                    <small>
                      {deliveryLabels[row.status] || '状态待核对'} · {row.detail}
                    </small>
                  </td>
                  <td>
                    <button onClick={() => visit(row.mandate_id, row.decision_id)}>
                      看委托与依据
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </main>
  )
}
export function PlannedPage({ kind }: { kind: 'framework' | 'evolution' }) {
  const framework = kind === 'framework'
  const headers = framework
    ? ['内容', '当前生效表述', '依据', '版本 / 日期', '操作']
    : ['候选改动', '对照与范围', '验证结果 / 限制', '状态', '操作']
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header}`}>
        <div>
          <h1>{framework ? '我的框架' : '验证与演进'}</h1>
          <p className={css.note}>{framework ? '明确偏好、判断与约定' : '候选与生效分开'}</p>
        </div>
      </header>
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              {headers.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} className={css.empty}>
                {framework
                  ? '框架记录尚未接入，暂不能读取或修改已确认的研究方法。'
                  : '验证记录尚未接入，暂不能查看对照、采用候选或回查修订。'}
                <small>此处没有可用数据，不代表你没有框架或验证记录。</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className={css.note}>
        {framework
          ? '推测兴趣不写入明确偏好；候选调整在验证与演进中单独确认。'
          : '未经验证与确认的候选不作为已生效规则。'}
      </p>
    </main>
  )
}
