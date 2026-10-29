import business from '../Business.module.css'
import { useEffect, useState } from 'react'
import { request, errorText } from '../shared/api.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { PersonalizationConfirm } from '../personalization/PersonalizationConfirm.js'
import type { PersonalPreview } from '../personalization/model.js'
import { fmt } from './types.js'
import form from '../Form.module.css'
type Report = {
  profile_is_explicit: boolean
  learning_enabled: boolean
  notice: string
  portfolio: {
    holdings_status: string
    profile_label: string
    note: string
    risk_budget: { single_stock_weight_max: number; hhi_max: number; portfolio_vol_max: number }
    summary: {
      n_positions: number | null
      equal_weight: number | null
      hhi: number | null
      shadow_max_drawdown: number | null
      shadow_annualized_vol: number | null
      data_note?: string
    }
  }
  alerts: {
    degraded: boolean
    items: {
      id: string
      source: string
      severity: string
      title: string
      detail: string
      ts: string
      mandate_id?: string
      feedback: { current?: string }
    }[]
  }
}
const percent = (n: number | null) => (n === null ? '未知' : `${fmt(n * 100)}%`)
const sources: Record<string, string> = {
  portfolio: '组合',
  shadow: '影子验证',
  event: '事件',
  profile: '画像预算',
  position_plan: '持仓目标',
}
export function PortfolioRiskPanel({
  version,
  visit,
}: {
  version: number
  visit?: (mid: string) => void
}) {
  const [data, setData] = useState<Report>(),
    [error, setError] = useState(''),
    [generation, setGeneration] = useState(0)
  const [preview, setPreview] = useState<PersonalPreview>(),
    [busy, setBusy] = useState(false)
  const refresh = () => setGeneration((n) => n + 1)
  useEffect(() => {
    const abort = new AbortController()
    void request<Report>('personalization', { operation: 'risk' }, abort.signal)
      .then((r) => {
        if (!abort.signal.aborted) {
          setData(r)
          setError('')
        }
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
    return () => abort.abort()
  }, [version, generation])
  const feedback = async (id: string, sentiment: string) => {
    setBusy(true)
    setError('')
    try {
      setPreview(
        await request('personalization', {
          operation: 'preview',
          action: 'feedback',
          card_id: id,
          sentiment,
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <FieldGroup
        title="组合风险与画像预算"
        hint="继承旧版等权集中度与影子净值模型；不是账户实时风险估值。"
      >
        <button onClick={refresh}>刷新风险记录</button>
        {error && <p role="alert">{error}</p>}
        {data ? (
          <>
            <p>{data.portfolio.note}</p>
            {data.portfolio.holdings_status === 'not_recorded' ? (
              <p>持仓尚未录入，不能据此判断空仓或风险达标。</p>
            ) : (
              <dl>
                <dt>持仓数 / 等权单仓占比</dt>
                <dd>
                  {fmt(data.portfolio.summary.n_positions)} /{' '}
                  {percent(data.portfolio.summary.equal_weight)}
                </dd>
                <dt>等权集中度 HHI</dt>
                <dd>{fmt(data.portfolio.summary.hhi)}</dd>
                <dt>影子最大回撤 / 年化波动</dt>
                <dd>
                  {percent(data.portfolio.summary.shadow_max_drawdown)} /{' '}
                  {percent(data.portfolio.summary.shadow_annualized_vol)}
                </dd>
              </dl>
            )}
            <p>
              {data.profile_is_explicit ? '当前确认画像' : '默认示例画像'}：
              {data.portfolio.profile_label} · 单仓预算{' '}
              {percent(data.portfolio.risk_budget.single_stock_weight_max)} · HHI{' '}
              {data.portfolio.risk_budget.hhi_max} · 波动预算{' '}
              {percent(data.portfolio.risk_budget.portfolio_vol_max)}
            </p>
            {data.portfolio.summary.data_note && <p>{data.portfolio.summary.data_note}</p>}
          </>
        ) : (
          <p role="status">正在读取组合风险…</p>
        )}
      </FieldGroup>
      {data && (
        <FieldGroup title="聚合风险预警" hint={data.notice}>
          {data.alerts.degraded && <p>事件来源为已保存快照，未保证实时或全市场完整覆盖。</p>}
          {!data.learning_enabled && <p>本机学习暂停中；可在「为我关注」启用反馈与偏好复盘。</p>}
          {data.alerts.items.map((item) => (
            <article key={item.id}>
              <small>
                {sources[item.source] || item.source} · {item.severity} · {item.ts}
              </small>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
              <div className={business.tools}>
                <button
                  disabled={busy || !data.learning_enabled}
                  aria-pressed={item.feedback?.current === 'useful'}
                  onClick={() => void feedback(item.id, 'useful')}
                >
                  值得关注
                </button>
                <button
                  disabled={busy || !data.learning_enabled}
                  aria-pressed={item.feedback?.current === 'useless'}
                  onClick={() => void feedback(item.id, 'useless')}
                >
                  减少此类
                </button>
                {item.feedback?.current && (
                  <button disabled={busy} onClick={() => void feedback(item.id, 'neutral')}>
                    撤销反馈
                  </button>
                )}
                {item.mandate_id && visit && (
                  <button onClick={() => visit(item.mandate_id!)}>查看联系与证据</button>
                )}
              </div>
            </article>
          ))}
        </FieldGroup>
      )}
      {preview && (
        <PersonalizationConfirm
          preview={preview}
          close={() => setPreview(undefined)}
          saved={() => {
            setPreview(undefined)
            refresh()
          }}
        />
      )}
    </>
  )
}
