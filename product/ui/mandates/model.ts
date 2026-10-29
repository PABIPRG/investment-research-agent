import type { ContactRule } from './ContactRuleEditor.js'
import type { Evidence, Execution, ResearchResult } from '../model.js'
export type Scope = { entity_id: string; exchange: string; operation: string; period?: string }
export type MandateView = {
  display_name?: string
  position_risk?: {
    kind: string
    basis_cost: number
    resolved_price: number
    reason?: string | null
  }
  mandate: { mandate_id: string; current_revision: number; status: string }
  generation: number
  requires_comparison_baseline?: boolean
  execution_mode?: 'program_price' | 'research'
  revision: {
    goal: string
    scope: Scope
    basis: {
      contact_rule?: ContactRule
      contact_note?: string
      entity_confirmation?: { label?: string }
    }
    contact_policy?: { reminder_time?: string; channels?: string[] }
  }
  contact_rule_description?: string
  baseline_revision?: number
  baseline: ResearchResult | null
  executions: Execution[]
  evidence: Evidence[]
  decisions?: ContactDecision[]
  results?: {
    job_id: string
    stale: boolean
    evidence_batch_id?: string | null
    structured_result: ResearchResult
  }[]
  notifications?: any[]
  sources?: any[]
  source_check?: { status: string; detail: string }
  monitoring: { enabled?: boolean; detail: string }
}
export const statuses: Record<string, string> = {
  tracking: '跟进中',
  paused: '已暂停',
  ended: '已结束',
  pending_requirements: '待补充',
  queued: '等待研究',
  running: '研究中',
  succeeded: '研究完成',
  failed: '研究失败',
  cancelled: '已撤销',
  interrupted: '研究中断',
}
const sourceReasons: Record<string, string> = {
  provider_timeout: '资料源响应超时',
  provider_failed: '资料源采集失败',
  requested_period_or_metric_not_covered: '来源没有覆盖指定期间或指标',
  requested_value_unavailable: '来源中的指标值缺失或无法作为数值使用',
  requested_metric_ambiguous: '来源对同一指标返回多条记录，口径尚不能确定',
  provider_schema_invalid: '来源返回的资料格式无法核验',
  no_source_records: '来源未返回记录',
  market_source_stale_or_partial: '行情已过期或所需字段缺失，暂不能判断条件',
  market_quote_price_time_or_subject_unavailable:
    '报价价格、单位、证券身份或来源时间无法核验，暂不能判断到价',
  market_source_unavailable: '行情来源暂不可用，系统会按约继续检查',
}
export function sourceReason(reason: string): string {
  return sourceReasons[reason] || reason
}

export type ContactDecision = {
  decision_id: string
  job_id?: string
  condition_result: string
  decision: string
  detail: string
  reason_code: string
  evidence_ref?: string
  created_at?: string
}
