import { FieldGroup } from '../shared/FieldGroup.js'
import type { Facts } from './types.js'
const percent = (n: number) => `${Math.round(n * 100)}%`
export function RiskPolicyView({ facts }: { facts: Facts }) {
  const policy = facts.risk_policy
  if (!policy) return null
  return (
    <FieldGroup
      title="当前风险预算与护栏"
      hint="继承旧版三档标准；预算是研究约束，不能据此认定当前组合已达标。"
    >
      <p>
        问卷推断：
        {
          (
            { conservative: '保守型', balanced: '稳健型', aggressive: '进取型' } as Record<
              string,
              string
            >
          )[policy.inferred_profile]
        }
        ；当前生效：{policy.label}
      </p>
      <dl>
        <dt>单股权重上限</dt>
        <dd>{percent(policy.risk_budget.single_stock_weight_max)}</dd>
        <dt>集中度 HHI 上限</dt>
        <dd>{policy.risk_budget.hhi_max}</dd>
        <dt>组合年化波动预算</dt>
        <dd>{percent(policy.risk_budget.portfolio_vol_max)}</dd>
        <dt>Beta 预算</dt>
        <dd>{policy.risk_budget.beta_max}</dd>
        <dt>建议护栏</dt>
        <dd>
          {policy.guardrail.buy_risk_score_max !== undefined
            ? `买入建议风险分超过 ${policy.guardrail.buy_risk_score_max} 时降级为持有`
            : `卖出建议风险分低于 ${policy.guardrail.sell_risk_score_min} 时按弱信号处理`}
        </dd>
      </dl>
      <p>未取得同口径风险分时不能执行护栏校正；未知风险不等于低风险。</p>
    </FieldGroup>
  )
}
