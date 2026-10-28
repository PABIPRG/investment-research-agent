export type Category = 'holdings' | 'watchlist' | 'strategies' | 'research' | 'mandates'
export type Rule = 'keep_local' | 'use_import'
export type TransferRequest = (body: Record<string, unknown>) => Promise<any>
export const labels: Record<Category, string> = {
  holdings: '持仓与历史成交',
  watchlist: '自选',
  strategies: '策略候选与旧验证档案',
  research: '旧研究与对话档案',
  mandates: '持续委托（暂停）',
}
export const effects: Record<Category, string> = {
  holdings: '合并当前持仓，历史成交只补记录，不重复计算持仓。',
  watchlist: '加入尚未收藏的证券，保留当前自选。',
  strategies: '保存为待重新验证的策略；旧收益与验证结果仅归档。',
  research: '保留只读资料，不恢复 DSH 会话或变成新研究证据。',
  mandates: '迁入后保持暂停，需重新核对范围与联系约定。',
}
export type Uploaded = {
  upload_id: string
  filename: string
  categories: { id: Category; label: string }[]
  warnings: string[]
  missing_attachments: string[]
}
export type Change = {
  category: Category
  kind: string
  name: string
  code?: string
  before: Record<string, unknown> | null
  after: Record<string, unknown>
}
export type Changes = { items: Change[]; total: number; offset: number; limit: number }
export type Preview = {
  preview_id: string
  request_key: string
  upload_id: string
  selected: Category[]
  rules: Partial<Record<Category, Rule>>
  status: string
  expires_at: number
  can_commit: boolean
  summary: Record<string, any>
  changes: Changes
  warnings: string[]
  blockers: { category: string; message: string }[]
  receipt?: any
}
export function failure(error: unknown) {
  return error instanceof Error ? error.message : '暂时无法连接，请重试读取状态。'
}
const fieldLabels: Record<string, string> = {
  quantity: '数量',
  cost_price: '单位成本',
  side: '方向',
  price: '成交价',
  fees: '费用',
  traded_at: '成交时间',
  affects_holdings: '更新持仓',
  reason: '备注',
  kind: '规则',
  params: '参数',
  symbols: '证券',
  rationale: '假设',
  status: '状态',
  scope: '范围',
  external_contact_authorized: '外部联系许可',
}
export function describe(value: Record<string, unknown> | null): string {
  if (value === null) return '当前没有此记录'
  return Object.entries(value)
    .map(([key, raw]) => {
      const item =
        raw === null
          ? '未知'
          : raw === false
            ? '否'
            : raw === true
              ? '是'
              : raw === 'buy'
                ? '买入'
                : raw === 'sell'
                  ? '卖出'
                  : raw === 'candidate'
                    ? '待验证'
                    : raw === 'paused'
                      ? '暂停'
                      : typeof raw === 'object'
                        ? JSON.stringify(raw)
                        : String(raw)
      return `${fieldLabels[key] ?? key}：${item}`
    })
    .join('；')
}
