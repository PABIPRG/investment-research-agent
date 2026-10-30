import { useSnapshot } from '../shared/useSnapshot.js'
import { ApiError } from '../shared/api.js'
import type { MandateView } from '../mandates/model.js'
type Snapshot = { items: MandateView[]; next_cursor?: string | null }
async function load(signal: AbortSignal): Promise<Snapshot> {
  const response = await fetch('api/huohuo/mandates', { signal, cache: 'no-store' })
  if (!response.ok)
    throw new ApiError(
      response.status === 401
        ? '登录已失效，请重新打开本机认证入口。'
        : response.status === 403
          ? '无权读取当前实例的委托。'
          : '委托进展暂时无法读取，请刷新重试。',
      response.status,
    )
  const data = await response.json()
  if (!Array.isArray(data.items)) throw Error('委托进展格式暂不可用。')
  return data
}
/** Reuse product read isolation: background polling keeps controls and snapshots stable. */
export function useActivityMandates() {
  const snapshot = useSnapshot<Snapshot>('activity-mandates', load, { pollMs: () => 30000 })
  return {
    items: snapshot.data?.items ?? [],
    complete: snapshot.data !== undefined && snapshot.data.next_cursor == null,
    at: snapshot.at,
    error: snapshot.error,
    loading: snapshot.loading,
    refreshing: snapshot.refreshing,
    refresh: snapshot.refresh,
  }
}
