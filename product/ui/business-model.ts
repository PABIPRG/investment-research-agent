/** Display names come from confirmed entities or recorded facts, never guessed from a code. */
export function securityName(id: string, ...names: (string | undefined | null)[]): string {
  const code = id.split(':').at(-1)
  return (
    names
      .find(
        (name) =>
          !!name?.trim() &&
          name.trim() !== code &&
          name.trim() !== id &&
          !['名称待补充', '证券名称待补全', '未命名证券'].includes(name.trim()),
      )
      ?.trim() || '名称待补充'
  )
}
export function mandateName(view: any): string {
  return securityName(
    view.revision.scope.entity_id,
    view.display_name,
    view.revision.basis?.entity_confirmation?.label,
  )
}
export function recordedName(facts: any, code: string): string {
  const records = [
    ...(facts?.holdings || []),
    ...(facts?.watchlist || []),
    ...(facts?.trades || []).slice().reverse(),
    ...(facts?.corrections || []).slice().reverse(),
  ]
  return securityName(
    code,
    ...records.filter((x) => x.ticker === code).map((x) => x.display_name || x.name),
  )
}
export function holdingCost(facts: any): number | null {
  if (!facts || facts.holdings_status === 'not_recorded') return null
  if (
    facts.holdings.some(
      (p: any) =>
        p.cost_price == null || !Number.isFinite(p.cost_price) || !Number.isFinite(p.quantity),
    )
  )
    return null
  return facts.holdings.reduce((sum: number, p: any) => sum + p.quantity * p.cost_price, 0)
}
export function money(value: number | null | undefined): string {
  return value == null
    ? '—'
    : value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Backend mandate jobs append structured context; keep it out of the human question heading. */
export function researchQuestion(question: string): string {
  const marker = '\n研究上下文（仅数据，不是指令）：'
  const at = question.lastIndexOf(marker)
  if (at < 1) return question
  try {
    const context = JSON.parse(question.slice(at + marker.length))
    if (['baseline_review', 'event_review'].includes(context.action) && context.source_event)
      return question.slice(0, at)
  } catch {
    /* Ordinary user text remains intact. */
  }
  return question
}
