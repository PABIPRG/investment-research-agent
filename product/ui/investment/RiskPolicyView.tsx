import { InvestmentSection } from './InvestmentSection.js'
import ui from './Sections.module.css'
import type { Facts } from './types.js'
const percent = (n: number) => `${Math.round(n * 100)}%`
export function RiskPolicyView({ facts }: { facts: Facts }) {
  const p = facts.risk_policy
  if (!p) return null
  const inferred = (
    { conservative: '保守型', balanced: '稳健型', aggressive: '进取型' } as Record<string, string>
  )[p.inferred_profile]
  return (
    <InvestmentSection
      title="研究预算与建议校准"
      hint="预算用于约束研究，不能据此认定当前组合已达标。"
    >
      <p className={ui.muted}>
        问卷推断：{inferred} · 当前生效：{p.label}
      </p>
      <dl className={ui.metrics}>
        <div>
          <dt>单股权重上限</dt>
          <dd>{percent(p.risk_budget.single_stock_weight_max)}</dd>
        </div>
        <div>
          <dt>集中度 HHI 上限</dt>
          <dd>{p.risk_budget.hhi_max}</dd>
        </div>
        <div>
          <dt>组合年化波动预算</dt>
          <dd>{percent(p.risk_budget.portfolio_vol_max)}</dd>
        </div>
        <div>
          <dt>Beta 预算</dt>
          <dd>{p.risk_budget.beta_max}</dd>
        </div>
      </dl>
      <details className={ui.disclosure}>
        <summary>查看建议校准规则</summary>
        <div>
          <p>
            {p.guardrail.buy_risk_score_max !== undefined
              ? `买入建议风险分超过 ${p.guardrail.buy_risk_score_max} 时降级为持有`
              : `卖出建议风险分低于 ${p.guardrail.sell_risk_score_min} 时按弱信号处理`}
            。
          </p>
          <p className={ui.muted}>未取得同口径风险分时不能校正；未知风险不等于低风险。</p>
        </div>
      </details>
    </InvestmentSection>
  )
}
