import type { ContactDecision, MandateView } from './model.js'
/** Resolve only explicit IDs. Never associate evidence by nearby timestamps or list positions. */
export function decisionContext(current: MandateView, decision: ContactDecision) {
  const candidates = (current.results || []).filter(
    (r) => !!decision.job_id && r.job_id === decision.job_id && !r.stale,
  )
  const matched = candidates.filter(
    (r) =>
      decision.evidence_ref &&
      (r.evidence_batch_id === decision.evidence_ref ||
        r.structured_result.evidence_ids?.includes(decision.evidence_ref)),
  )
  const result =
    matched.length === 1
      ? matched[0]
      : !decision.evidence_ref && candidates.length === 1
        ? candidates[0]
        : undefined
  const ids =
    decision.evidence_ref && current.evidence.some((e) => e.evidence_id === decision.evidence_ref)
      ? [decision.evidence_ref]
      : result?.structured_result.evidence_ids || []
  const evidence = current.evidence.filter((e) => ids.includes(e.evidence_id))
  return {
    result: result?.structured_result,
    evidence,
    missing: ids.some((id) => !evidence.some((e) => e.evidence_id === id)),
  }
}
export function contactOutcome(decision: string) {
  return (
    (
      {
        send: '已安排提醒，送达状态见下方',
        suppress: '本次不另行提醒',
        defer: '暂缓提醒',
        aggregate: '已纳入汇总，送达状态见下方',
      } as Record<string, string>
    )[decision] || '提醒处理状态待核对'
  )
}
