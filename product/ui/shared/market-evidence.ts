import type { Evidence } from '../model.js'

const fields = [
  ['price', '报价', 'CNY/share', '元/股'],
  ['previous_close', '昨收', 'CNY/share', '元/股'],
  ['pct_change', '较昨收变化', '%', '%'],
  ['volume_ratio', '量比', 'ratio', '倍'],
  ['turnover', '换手率', '%', '%'],
  ['amount_yi', '成交额', '1e8 CNY', '亿元'],
] as const

export function marketQuoteRows(row: Evidence) {
  if (row.scope?.operation !== 'market_quote' || !Array.isArray(row.values?.items)) return []
  return row.values.items.map((item) => {
    const units = item.units as Record<string, unknown> | undefined
    return {
      name: String(item.name || item.code || '证券'),
      asOf: item.time_known === true && typeof item.as_of === 'string' ? item.as_of : undefined,
      stale: item.stale !== false,
      facts: fields.map(([key, label, unit, displayUnit]) => ({
        label: units?.[key] === unit ? `${label}（${displayUnit}）` : `${label}（单位未核验）`,
        value:
          typeof item[key] === 'number' && Number.isFinite(item[key]) ? String(item[key]) : '—',
      })),
    }
  })
}
