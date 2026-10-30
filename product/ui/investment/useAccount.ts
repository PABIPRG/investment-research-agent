import { useCallback, useEffect, useRef, useState } from 'react'
import { errorText, request } from '../shared/api.js'
import type { AccountView } from './account-model.js'
export function useAccount() {
  const [account, setAccount] = useState<AccountView>(),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(true)
  const hasData = useRef(false)
  const [refreshing, setRefreshing] = useState(false)
  const generation = useRef(0)
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current
    const active = () => !signal?.aborted && current === generation.current
    setLoading(!hasData.current)
    try {
      const value = await request<AccountView>('investment-account', undefined, signal)
      if (active()) {
        hasData.current = true
        setAccount(value)
        setError('')
      }
    } catch (e) {
      if (active()) setError(errorText(e))
    } finally {
      if (active()) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])
  useEffect(() => {
    const abort = new AbortController()
    const changed = () => void refresh(abort.signal)
    changed()
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') changed()
    }, 60000)
    window.addEventListener('huohuo-investment-changed', changed)
    return () => {
      generation.current++
      abort.abort()
      window.clearInterval(timer)
      window.removeEventListener('huohuo-investment-changed', changed)
    }
  }, [refresh])
  return {
    account,
    error,
    loading,
    refreshing,
    refresh: () => {
      setRefreshing(true)
      void refresh()
    },
  }
}
