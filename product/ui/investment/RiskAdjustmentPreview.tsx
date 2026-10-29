import { FieldGroup } from '../shared/FieldGroup.js'
import { toleranceLabel } from './risk-adjustment-model.js'
import type { Facts } from './types.js'
import css from './RiskAdjustment.module.css'

const percent = (value?: number) => (value === undefined ? '未设置' : `${Math.round(value * 100)}%`)

export function RiskAdjustmentPreview({
  before,
  after,
  risk,
  years,
}: {
  before: Facts
  after: Facts
  risk: number
  years: string
}) {
  const label = toleranceLabel(risk)
  const adjusted = after.risk_profile?.label !== label + '型'
  return (
    <>
      <FieldGroup title="核对你的选择">
        <dl className={css.effects}>
          <div>
            <dt>接受波动的意愿</dt>
            <dd>{label}</dd>
          </div>
          <div>
            <dt>资金预计使用时间</dt>
            <dd>{years} 年后</dd>
          </div>
        </dl>
      </FieldGroup>
      <FieldGroup
        title="保存后生效的偏好"
        hint="火火会综合你的选择与投资期限，按现有规则确定档位。"
      >
        <div className={css.outcome}>
          <span>当前：{before.risk_profile?.label}</span>
          <strong>调整后：{after.risk_profile?.label}</strong>
        </div>
        {adjusted && (
          <p className={css.notice}>
            {Number(years) < 2
              ? '预计不足两年使用资金时，现有规则将最终档位限制在稳健型及以下，因此本次不会按进取型生效。'
              : '预计五年及以上使用资金时，现有规则将最终档位设为稳健型及以上，因此本次保守意愿会按稳健型生效。'}
            该结果来自现有期限规则；如不接受，可以取消本次调整。
          </p>
        )}
      </FieldGroup>
      {after.risk_policy && (
        <FieldGroup
          title="研究提示将如何变化"
          hint="以下是研究使用的参考上限，不是对收益或损失的承诺，也不会自动调整实际仓位。"
        >
          <dl className={css.effects}>
            <div>
              <dt>单只股票仓位参考上限</dt>
              <dd>
                {percent(before.risk_policy?.risk_budget.single_stock_weight_max)} →{' '}
                {percent(after.risk_policy.risk_budget.single_stock_weight_max)}
              </dd>
            </div>
            <div>
              <dt>组合年化波动参考上限</dt>
              <dd>
                {percent(before.risk_policy?.risk_budget.portfolio_vol_max)} →{' '}
                {percent(after.risk_policy.risk_budget.portfolio_vol_max)}
              </dd>
            </div>
          </dl>
        </FieldGroup>
      )}
      <p className={css.note}>
        确认后更新当前偏好，并保留原问卷与调整历史。持仓、已有委托和提醒约定保持原状。
      </p>
    </>
  )
}
