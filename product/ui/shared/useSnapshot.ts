import { useCallback, useEffect, useRef, useState } from 'react'
import { ReadCycle } from './read-cycle.js'
import { ApiError, errorText } from './api.js'

/** Background reads preserve controls, drafts and the last successful snapshot. */
export function useSnapshot<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
  options: { pollMs?: (data: T) => number | undefined; paused?: boolean } = {},
) {
  const [data, setData] = useState<T>(),
    [loading, setLoading] = useState(true),
    [refreshing, setRefreshing] = useState(false),
    [error, setError] = useState(''),
    [at, setAt] = useState(0)
  const cycle = useRef(new ReadCycle()),
    current = useRef({ data, load, options }),
    timer = useRef<ReturnType<typeof setTimeout>>(),
    mounted = useRef(false)
  current.current = { data, load, options }
  const read = useCallback(async (manual = false) => {
    if (!mounted.current || current.current.options.paused) return
    if (cycle.current.pending) {
      if (manual) setRefreshing(true)
      return
    }
    clearTimeout(timer.current)
    const ticket = cycle.current.begin()
    setLoading(current.current.data === undefined)
    setRefreshing(manual)
    try {
      const next = await current.current.load(ticket.signal)
      if (ticket.current()) {
        current.current.data = next
        setData(next)
        setAt(Date.now() / 1000)
        setError('')
      }
    } catch (e) {
      if (ticket.current()) {
        setError(errorText(e))
        if (
          (e instanceof ApiError && e.status === 403) ||
          (e as { http_status?: number })?.http_status === 403
        ) {
          current.current.data = undefined
          setData(undefined)
        }
      }
    } finally {
      if (ticket.current()) {
        ticket.finish()
        setLoading(false)
        setRefreshing(false)
        const value = current.current.data
        const delay = value === undefined ? 30000 : current.current.options.pollMs?.(value)
        if (delay && mounted.current)
          timer.current = setTimeout(() => {
            if (document.visibilityState === 'visible') void read()
          }, delay)
      }
    }
  }, [])
  const invalidate = useCallback(() => {
    clearTimeout(timer.current)
    cycle.current.invalidate()
    setRefreshing(false)
    setLoading(false)
  }, [])
  const replace = useCallback(
    (update: T | ((old: T | undefined) => T | undefined)) => {
      invalidate()
      const next =
        typeof update === 'function'
          ? (update as (old?: T) => T | undefined)(current.current.data)
          : update
      current.current.data = next
      setData(next)
      setAt(Date.now() / 1000)
    },
    [invalidate],
  )
  useEffect(() => {
    mounted.current = true
    cycle.current.invalidate()
    void read()
    const visible = () => {
      if (document.visibilityState === 'visible') void read()
    }
    document.addEventListener('visibilitychange', visible)
    return () => {
      mounted.current = false
      clearTimeout(timer.current)
      cycle.current.invalidate()
      document.removeEventListener('visibilitychange', visible)
    }
  }, [key, read])
  useEffect(() => {
    if (options.paused) invalidate()
    else void read()
  }, [options.paused, invalidate, read])
  return {
    data,
    loading,
    refreshing,
    error,
    at,
    replace,
    invalidate,
    refresh: () => void read(true),
    revalidate: () => void read(),
  }
}
