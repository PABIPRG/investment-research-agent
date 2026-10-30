import { useEffect, useState } from 'react'
import type { MandateView } from '../mandates/model.js'
/** Independent from notification reads; failed refreshes preserve the last successful snapshot. */
export function useActivityMandates(refresh: number) {
  const [state, setState] = useState({
    items: [] as MandateView[],
    complete: false,
    at: 0,
    error: '',
    loading: true,
  })
  useEffect(() => {
    const controller = new AbortController()
    setState((old) => ({ ...old, loading: true }))
    void fetch('api/huohuo/mandates', { signal: controller.signal, cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok)
          throw Error(
            response.status === 401
              ? '登录已失效，请重新打开本机认证入口。'
              : response.status === 403
                ? '无权读取当前实例的委托。'
                : '委托进展暂时无法读取，请刷新重试。',
          )
        const data = await response.json()
        if (!Array.isArray(data.items)) throw Error('委托进展格式暂不可用。')
        if (!controller.signal.aborted)
          setState({
            items: data.items,
            complete: data.next_cursor == null,
            at: Date.now() / 1000,
            error: '',
            loading: false,
          })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState((old) => ({ ...old, loading: false, error: error.message }))
      })
    return () => controller.abort()
  }, [refresh])
  return state
}
