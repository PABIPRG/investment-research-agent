export type TargetKind = 'take_profit' | 'stop_loss'
export type RuleTarget = { enabled: boolean; mode: 'percent' | 'price'; value: number | null }
export type RiskConfig = {
  take_profit: RuleTarget
  stop_loss: RuleTarget
  monitoring_disabled: boolean
  effective_at: string | null
  expires_at: string | null
  version?: number
}
export type PositionRiskView = {
  global_status: string
  config: { global: RiskConfig | null; overrides: Record<string, RiskConfig> }
  suggestion?: { take_profit_pct: number; stop_loss_pct: number } | null
  notice: string
  plans: {
    ticker: string
    name?: string
    source: string
    status: string
    basis_changed: boolean
    errors?: string[]
    targets: Partial<
      Record<
        TargetKind,
        {
          mandate_id: string
          basis_cost: number
          resolved_price: number
          generation: number
          status: string
        }
      >
    >
  }[]
}
export type RiskEdit = {
  operation: 'global' | 'override' | 'remove_override' | 'rearm'
  ticker?: string
  kind?: TargetKind
}
export const riskStatus: Record<string, string> = {
  invalid_target: '绝对目标价与当前成本方向不符，需修改配置',
  active: '生效',
  scheduled: '等待生效',
  unconfigured: '未配置',
  disabled: '已停用',
  cost_unknown: '成本未知或非正，尚未激活',
  expired: '已到期',
  triggered: '已触发，需明确重新布防',
  tracking: '跟进中',
  paused: '已暂停',
  ended: '已结束',
  modified: '已在委托中改约，请重新核对风险计划',
}
export const targetNames: Record<TargetKind, string> = { take_profit: '止盈', stop_loss: '止损' }
