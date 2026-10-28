export const ruleLabels: Record<string, string> = {
  ma_cross: '均线交叉',
  momentum: '动量',
  rsi_reversal: 'RSI 反转',
  breakout: '通道突破',
  bollinger: '布林带',
  volume_breakout: '放量突破',
}
export const participation: Record<string, string> = {
  candidate: '待回测',
  active: '参与验证',
  retired: '已停止',
  rejected: '未采用',
}
export const verification: Record<string, string> = {
  passed: '样本外达标',
  not_passed: '样本外未达标',
  insufficient: '样本不足',
}
export const actionLabels: Record<string, string> = {
  schedule: '更新后台计划',
  accept_suggestion: '保存候选建议',
  recall: '归档召回建议',
  events: '读取策略相关新闻',
  create: '保存策略',
  backtest: '运行回测',
  shadow: '更新影子验证',
  evolve: '生成进化预案',
  apply: '应用预案',
  retire: '停止验证',
}
export const runLabels: Record<string, string> = {
  pending: '排队中',
  running: '计算中',
  completed: '已完成',
  skipped: '本次无需执行',
  failed: '未完成',
  cancelled: '已停止',
  interrupted: '重启中断',
}
export const defaults: Record<string, Record<string, number>> = {
  ma_cross: { fast: 5, slow: 20 },
  momentum: { n: 10 },
  rsi_reversal: { n: 14, oversold: 30, overbought: 70 },
  breakout: { n: 20 },
  bollinger: { n: 20, k: 2 },
  volume_breakout: { n: 20, vol_mult: 1.5 },
}
export const paramLabels: Record<string, string> = {
  fast: '快均线天数',
  slow: '慢均线天数',
  n: '观察天数',
  oversold: '超卖线',
  overbought: '超买线',
  k: '标准差倍数',
  vol_mult: '成交量倍数',
}
export type Strategy = {
  id: string
  revision: number
  name: string
  kind: string
  params: Record<string, number>
  securities: { code: string; name: string }[]
  symbols: string[]
  rationale?: string
  status: string
  verification_status: string
  backtest: any
  updated_at: string
}
export type Run = {
  subjects?: string[]
  id: string
  strategy_id: string
  action: string
  status: string
  created_at: number
  updated_at: number
  error?: string
  evidence: any[]
  result: any
}
export type StrategyView = {
  strategies: Strategy[]
  pool: any
  attribution: any
  preview: any
  previews?: Record<string, any>
  state_version: string
  runs: Run[]
  model_note: string
  shadow_series?: any[]
  automation?: StrategySchedule & { next_at?: number; updated_at?: number }
  suggestions?: {
    id: string
    status: string
    source_kind: string
    created_at: number
    document: { candidate: Strategy; evidence: any[] }
  }[]
  background_jobs?: {
    id: string
    strategy_id: string
    action: string
    status: string
    updated_at: number
    error?: string
  }[]
  planner_jobs?: { id: string; status: string; updated_at: number; error?: string }[]
}
export type StrategySchedule = {
  revision: number
  enabled: boolean
  daily_time: string
  strategy_ids: string[]
  actions: string[]
  retest_days: number
  lookback_days: number
  event_candidates: boolean
  archive_recall: boolean
}
export type Edit = {
  action: string
  strategy?: Strategy
  token?: string
  poolVersion?: string
  payload?: Record<string, unknown>
  schedule?: StrategySchedule
  strategies?: Strategy[]
}
export const pct = (value: number | null | undefined) =>
  value == null ? '—' : `${value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}%`
export const instant = (value: number | string) =>
  new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString('zh-CN')
export function previewState(value: any) {
  return (
    (
      {
        none: '尚无预案',
        pending: '待确认',
        stale: '依据已变化，需重新生成',
        expired: '已过期，需重新生成',
        applied: '已应用',
      } as Record<string, string>
    )[value?.preview_status] ?? '状态待核对'
  )
}

export function resultNotice(result: any, action: string) {
  if (result.run.status === 'skipped')
    return result.run.result?.skipped || '本次按市场环境跳过，未写入模拟收益。'
  if (result.run.status !== 'completed')
    return `${actionLabels[action]}未完成：${result.run.error || '请查看运行记录。'} 已保存的策略与结果保持不变。`
  if (result.evolution && !result.evolution.actions?.length)
    return result.evolution.data_note || '本次检查已完成，当前没有需要确认的调整动作。'
  if (result.backtest) return result.backtest.reason + '；可以查看样本内外结果与行情依据。'
  return actionLabels[action] + '已完成，可查看记录与依据。'
}
