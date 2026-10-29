import business from '../Business.module.css'
import { recordedName } from '../business-model.js'
import { useEffect, useState } from 'react'
import { request } from '../shared/api.js'
import { InvestmentSection as FieldGroup } from './InvestmentSection.js'
import { RiskPlanEditor } from './RiskPlanEditor.js'
import { PortfolioRiskPanel } from './PortfolioRiskPanel.js'
import { riskStatus, targetNames, type RiskEdit, type TargetKind } from './position-risk-model.js'
import { fmt, type Facts } from './types.js'
import ui from './Sections.module.css'
export function PositionRiskPlans({
  facts,
  visit,
  refreshKey = 0,
}: {
  facts: Facts
  refreshKey?: number
  visit?: (mid: string) => void
}) {
  const [edit, setEdit] = useState<RiskEdit>()
  const [latest, setLatest] = useState<Facts['position_risk']>()
  const [statusError, setStatusError] = useState('')
  useEffect(() => {
    const abort = new AbortController()
    setLatest(undefined)
    const refresh = () =>
      void request<Facts>('investment', undefined, abort.signal)
        .then((current) => {
          if (abort.signal.aborted) return
          if (current.version === facts.version) {
            setLatest(current.position_risk)
            setStatusError('')
          } else window.dispatchEvent(new Event('huohuo-investment-changed'))
        })
        .catch(() => {
          if (!abort.signal.aborted)
            setStatusError('风险状态刷新失败，以下为上次记录；请用顶部刷新核对。')
        })
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => {
      clearInterval(timer)
      abort.abort()
    }
  }, [facts.version, refreshKey])
  const view = latest || facts.position_risk
  if (!view) return <p role="alert">当前后端未提供持仓风险计划，请确认实例版本后重试。</p>
  return (
    <section aria-label="持仓风险计划" className={ui.stack}>
      {statusError && <p role="alert">{statusError}</p>}
      <FieldGroup
        title="持仓止盈止损"
        hint="按激活时成本设定目标，成本变化后需明确重新布防；触发后仅提醒，不下单。"
        actions={
          <button data-variant="primary" onClick={() => setEdit({ operation: 'global' })}>
            {view.config.global ? '调整全局止盈止损' : '设置全局止盈止损'}
          </button>
        }
      >
        <p>
          全局配置：
          {view.config.global ? riskStatus[view.global_status] || view.global_status : '尚未配置'}
          。可在委托中回查触发依据与提醒记录。
        </p>
        {!view.plans.length && (
          <p>当前没有已记录持仓。可先设置全局约定，在后续明确录入持仓后应用。</p>
        )}
      </FieldGroup>
      {view.plans.map((plan) => (
        <FieldGroup
          key={plan.ticker}
          title={`${recordedName(facts, plan.ticker)}（${plan.ticker}）`}
          hint={`${plan.source === 'override' ? '使用单仓覆盖' : '继承全局'} · ${riskStatus[plan.status] || plan.status}`}
        >
          {plan.basis_changed && (
            <p role="status">
              当前成本与激活快照不同，原阈值保持不变；需要按新成本更新时，请明确重新布防。
            </p>
          )}
          {plan.errors?.map((message, i) => (
            <p role="status" key={i}>
              {message}
            </p>
          ))}
          <div className={ui.targets}>
            {(['take_profit', 'stop_loss'] as TargetKind[]).map((kind) => {
              const target = plan.targets[kind]
              return (
                <div key={kind}>
                  <strong>{targetNames[kind]}</strong>
                  {target ? (
                    <>
                      <p className={ui.targetValue}>{fmt(target.resolved_price)} 元</p>
                      <p className={ui.muted}>
                        激活成本 {fmt(target.basis_cost)} 元 ·{' '}
                        {riskStatus[target.status] || target.status}
                      </p>
                      <details>
                        <summary>查看激活信息</summary>
                        <p>当前目标第 {target.generation} 代；重新布防会撤销旧代次资格。</p>
                      </details>
                      <div className={business.tools}>
                        <button
                          onClick={() => setEdit({ operation: 'rearm', ticker: plan.ticker, kind })}
                          disabled={plan.status !== 'active'}
                        >
                          重新布防{targetNames[kind]}
                        </button>
                        {visit && (
                          <button onClick={() => visit(target.mandate_id)}>查看对应委托</button>
                        )}
                      </div>
                    </>
                  ) : (
                    <p>尚未激活此目标。</p>
                  )}
                </div>
              )
            })}
          </div>
          <div className={business.tools}>
            <button onClick={() => setEdit({ operation: 'override', ticker: plan.ticker })}>
              设置单仓覆盖
            </button>
            {plan.source === 'override' && (
              <button
                onClick={() => setEdit({ operation: 'remove_override', ticker: plan.ticker })}
              >
                删除覆盖，继承全局
              </button>
            )}
          </div>
        </FieldGroup>
      ))}
      <details className={ui.disclosure}>
        <summary>查看持仓目标规则</summary>
        <div>
          <p>{view.notice}</p>
        </div>
      </details>
      <PortfolioRiskPanel version={facts.version} visit={visit} refreshKey={refreshKey} />
      {edit && (
        <RiskPlanEditor
          view={view}
          edit={edit}
          name={edit.ticker ? recordedName(facts, edit.ticker) : undefined}
          close={() => setEdit(undefined)}
        />
      )}
    </section>
  )
}
