import type { Security } from './types.js'
export type SearchResult = {
  status: 'ok' | 'empty' | 'unavailable' | 'stale'
  usable_for_confirmation: boolean
  candidates: Security[]
}
export function selectableSecurities(result: SearchResult): Security[] {
  return result.status === 'ok' && result.usable_for_confirmation ? result.candidates : []
}
export function searchMessage(result: SearchResult): string {
  return result.status === 'empty'
    ? '未找到匹配的沪深 A 股，请换一个名称或代码。'
    : result.status === 'stale'
      ? '搜索资料已过期，请重试后再选择。'
      : result.status !== 'ok' || !result.usable_for_confirmation
        ? '证券资料暂时无法读取，请重试；这不代表证券不存在。'
        : ''
}
