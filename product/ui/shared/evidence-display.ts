import type { Evidence, ResearchResult } from '../model.js'
export function sourceName(source?: string) {
  return (
    (
      {
        eastmoney: '东方财富',
        'akshare.stock_financial_abstract': '新浪财经 · 财务摘要',
        'akshare.stock_profile_cninfo': '巨潮资讯 · 公司资料',
      } as Record<string, string>
    )[source || ''] || (source && !/[._]/.test(source) ? source : '资料来源')
  )
}
export function periodName(value?: string) {
  if (!value) return '报告期未提供'
  if (/^\d{8}$/.test(value))
    return `${value.slice(0, 4)} 年 ${Number(value.slice(4, 6))} 月 ${Number(value.slice(6, 8))} 日`
  return value
}
export function evidenceTitle(row: Evidence) {
  const metric = row.values?.metric || row.scope?.metric
  if (metric) return `${periodName(row.values?.period || row.scope?.period)} · ${metric}`
  if (row.values?.profile) return `${row.values?.name || '公司'}资料`
  if (row.values?.price != null) return `${row.values.name || '证券'}报价`
  if (row.scope?.operation === 'market_quote') return '本次行情依据'
  return `${sourceName(row.source)}记录`
}
export const judgementLabels: Record<string, string> = {
  met: '已满足约定条件',
  unmet: '尚未满足约定条件',
  unknown: '资料不足，暂不能判断',
  error: '本次未能完成判断',
}
export function researchFinding(result?: ResearchResult | null) {
  const judgement = result?.judgements?.notable_change
  if (judgement)
    return {
      title: judgementLabels[judgement.judgement] || '判断状态待核对',
      detail: judgement.reason || '这次研究没有提供具体判断理由。',
    }
  if (result?.error) return { title: '研究没有完成', detail: result.error }
  return {
    title: result?.summary ? '本次研究结果' : '尚无可阅读的结论',
    detail: result?.summary || '记录中没有保存结论，可展开查看已获取的资料。',
  }
}
