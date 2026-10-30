import { useSyncExternalStore } from 'react'
import { acknowledge, ingest, type Feed, type ReminderState } from './model.js'
const listeners = new Set<() => void>()
let state: ReminderState = { scope: '', seen: [], pending: [] }
let owned = false,
  busy = false,
  timer: ReturnType<typeof setInterval> | undefined
let release: (() => void) | undefined,
  claiming = false,
  lastFeed: Feed | undefined
let snapshot = { ...state, owned }
const tab = Math.random().toString(36).slice(2)
const cacheKey = () => `huohuo.reminders.v1:${state.scope}`
function emit() {
  snapshot = { ...state, owned }
  for (const fn of listeners) fn()
}
function cached(scope: string): { seen: string[]; pending: string[] } {
  try {
    const value = JSON.parse(localStorage.getItem(`huohuo.reminders.v1:${scope}`) || '{}')
    const ids = (v: unknown): string[] =>
      Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(-1000) : []
    return { seen: ids(value.seen), pending: ids(value.pending) }
  } catch {
    return { seen: [], pending: [] }
  }
}
function persist() {
  try {
    localStorage.setItem(
      cacheKey(),
      JSON.stringify({ seen: state.seen, pending: state.pending.map((r) => r.id) }),
    )
  } catch {}
}
function relinquish() {
  release?.()
  release = undefined
  owned = false
  emit()
}
async function claim() {
  if (claiming || owned || !state.pending.length || document.hidden) return
  const scope = state.scope
  if (navigator.locks) {
    claiming = true
    void navigator.locks
      .request(`huohuo-reminder:${scope}`, { ifAvailable: true }, async (lock) => {
        claiming = false
        if (!lock || state.scope !== scope || document.hidden || !state.pending.length) return
        owned = true
        emit()
        await new Promise<void>((resolve) => {
          release = resolve
        })
      })
      .catch(() => {
        claiming = false
      })
  } else {
    // Older browsers: short owner lease, confirmed before rendering. No business sends occur here.
    try {
      const key = cacheKey() + ':lease',
        now = Date.now()
      const previous = JSON.parse(localStorage.getItem(key) || '{}')
      if (previous.until > now && previous.tab !== tab) return
      localStorage.setItem(key, JSON.stringify({ tab, until: now + 7000 }))
      setTimeout(() => {
        const holder = JSON.parse(localStorage.getItem(key) || '{}')
        if (holder.tab !== tab || document.hidden || state.scope !== scope) return
        owned = true
        release = () => {
          if (JSON.parse(localStorage.getItem(key) || '{}').tab === tab)
            localStorage.removeItem(key)
        }
        emit()
      }, 100)
    } catch {
      owned = true
      emit()
    }
  }
}
export async function refreshReminders() {
  if (busy || document.hidden) return
  busy = true
  try {
    const response = await fetch('api/huohuo/app-notifications', {
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    })
    if (response.status === 403) {
      state = { scope: '', seen: [], pending: [] }
      lastFeed = undefined
      relinquish()
      return
    }
    if (!response.ok) return
    const feed: Feed = await response.json()
    if (!/^[a-f0-9]{32}$/.test(feed.scope) || !Array.isArray(feed.items)) return
    if (state.scope !== feed.scope) {
      relinquish()
      const saved = cached(feed.scope)
      state = {
        scope: feed.scope,
        seen: saved.seen.filter((id) => !saved.pending.includes(id)),
        pending: [],
      }
      state = ingest(state, feed, true, saved.pending)
    } else state = ingest(state, feed)
    lastFeed = feed
    persist()
    emit()
    void claim()
  } catch {
    /* Keep a pending prompt on a temporary outage; never invent or resend one. */
  } finally {
    busy = false
  }
}
export function respondReminder(id: string) {
  state = acknowledge(state, id)
  persist()
  emit()
  if (!state.pending.length) relinquish()
}
function sync(event: StorageEvent) {
  if (!lastFeed || event.key !== cacheKey()) return
  const saved = cached(state.scope)
  state = ingest(
    {
      scope: state.scope,
      seen: saved.seen.filter((id) => !saved.pending.includes(id)),
      pending: [],
    },
    lastFeed,
    true,
    saved.pending,
  )
  if (!state.pending.length) relinquish()
  emit()
  void claim()
}
function visibility() {
  if (document.hidden) relinquish()
  else {
    void refreshReminders()
    void claim()
  }
}
function subscribe(fn: () => void) {
  listeners.add(fn)
  if (listeners.size === 1) {
    void refreshReminders()
    timer = setInterval(() => {
      if (!navigator.locks && owned && !document.hidden) {
        try {
          localStorage.setItem(
            cacheKey() + ':lease',
            JSON.stringify({ tab, until: Date.now() + 7000 }),
          )
        } catch {}
      }
      void refreshReminders()
      void claim()
    }, 3000)
    window.addEventListener('storage', sync)
    window.addEventListener('focus', visibility)
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('huohuo-notification-test-sent', visibility)
  }
  return () => {
    listeners.delete(fn)
    if (!listeners.size) {
      clearInterval(timer)
      relinquish()
      window.removeEventListener('storage', sync)
      window.removeEventListener('focus', visibility)
      document.removeEventListener('visibilitychange', visibility)
      window.removeEventListener('huohuo-notification-test-sent', visibility)
    }
  }
}
export function useReminders() {
  return useSyncExternalStore(subscribe, () => snapshot)
}

export function reminderPresented(id: string) {
  try {
    return JSON.parse(localStorage.getItem(cacheKey() + ':presented') || '[]').includes(id)
  } catch {
    return false
  }
}
export function markReminderPresented(id: string) {
  try {
    const key = cacheKey() + ':presented'
    const ids = JSON.parse(localStorage.getItem(key) || '[]')
    localStorage.setItem(key, JSON.stringify([...new Set([...ids, id])].slice(-1000)))
  } catch {}
}
