export type CapabilityStatus = 'registered' | 'restricted' | 'unconnected'
export interface Capability {
  id: string
  title: string
  kind: 'tool' | 'skill'
  description: string
  category: string
  source: string
  status: CapabilityStatus
  note: string
  action?: 'investment' | 'strategy'
}
export interface CapabilityCatalog {
  items: Capability[]
  read_at: string
  scope: 'product-preset'
}
export const statusLabels: Record<CapabilityStatus, string> = {
  registered: '已注册',
  restricted: '受限制',
  unconnected: '待接入',
}
export function filterCapabilities(
  items: Capability[],
  query: string,
  kind: 'all' | Capability['kind'],
  status: 'all' | CapabilityStatus,
) {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return items.filter(
    (item) =>
      (kind === 'all' || item.kind === kind) &&
      (status === 'all' || item.status === status) &&
      words.every((word) =>
        `${item.title} ${item.id} ${item.description} ${item.category}`
          .toLocaleLowerCase()
          .includes(word),
      ),
  )
}

/** Prepare a real DSH draft; the user reviews it before submitting. */
export function usagePrompt(item: Capability) {
  if (item.status !== 'registered') return undefined
  if (item.id === 'huohuo-investment-facts' || item.id === 'read_investment_facts')
    return '请先读取我的持仓与自选，按已保存的投资记录帮我梳理当前情况。'
  if (item.action === 'strategy')
    return (
      '请先读取当前策略与验证记录，再帮我使用“' +
      item.title +
      '”。如果尚无策略，先和我确认研究假设、证券与规则。'
    )
  if (item.id === 'huohuo-mandates')
    return '我想交代一项持续研究，请先帮我确认研究对象、范围和联系约定。'
  return `我想使用“${item.title}”这项能力。请先确认需要补充的信息，再按这项能力的实际范围帮我处理。`
}
