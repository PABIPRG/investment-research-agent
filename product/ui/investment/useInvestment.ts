import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, errorText, request } from '../shared/api.js'
import type { Facts } from './types.js'
import { hydrateDisplayNames } from './display-names.js'
export function useInvestment() {
  const [facts, setFacts] = useState<Facts>(),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('')
  const generation = useRef(0)
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current
    const active = () => !signal?.aborted && current === generation.current
    setLoading(true)
    setError('')
    try {
      const next = await request<Facts>('investment', undefined, signal)
      if (active()) {
        setFacts(next)
        // Show saved quantities immediately; optional label lookup never blocks the table.
        void hydrateDisplayNames(
          next,
          (code) => {
            if (!active()) return Promise.reject(new Error('名称读取已停止'))
            return request('security-search', { query: code }, signal)
          },
          async () => {
            if (!active()) return
            const labeled = await request<Facts>('investment', undefined, signal)
            if (active()) setFacts((old) => (old && old.version > labeled.version ? old : labeled))
          },
        ).catch(() => {})
      }
    } catch (e) {
      if (active()) {
        setError(errorText(e))
        if (e instanceof ApiError && e.status === 403) setFacts(undefined)
      }
    } finally {
      if (active()) setLoading(false)
    }
  }, [])
  useEffect(() => {
    const abort = new AbortController()
    void refresh(abort.signal)
    const changed = () => void refresh(abort.signal)
    window.addEventListener('huohuo-investment-changed', changed)
    return () => {
      generation.current++
      abort.abort()
      window.removeEventListener('huohuo-investment-changed', changed)
    }
  }, [refresh])
  return { facts, loading, error, refresh: () => void refresh() }
}
