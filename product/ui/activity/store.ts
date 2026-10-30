import { useSyncExternalStore } from 'react'
import {
  rememberActivity,
  unseenActivity,
  type ActivityRecord,
  type SeenActivity,
} from './model.js'
const key = 'huohuo.activity-seen.v1'
const listeners = new Set<() => void>()
let snapshot = {
  items: [] as ActivityRecord[],
  count: 0,
  loaded: false,
  loading: true,
  refreshing: false,
  error: '',
}
let seen: SeenActivity = {}
let pending: Promise<void> | undefined
let timer: ReturnType<typeof setInterval> | undefined
function readSeen() {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || '{}')
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      seen = Object.fromEntries(Object.entries(value).filter(([, v]) => typeof v === 'string'))
    }
  } catch {}
  return seen
}
function emit() {
  snapshot = { ...snapshot, count: unseenActivity(snapshot.items, seen) }
  for (const listener of listeners) listener()
}
export function refreshActivity(manual = false): Promise<void> {
  if (document.hidden) return Promise.resolve()
  if (pending) {
    if (manual) {
      snapshot = { ...snapshot, refreshing: true }
      emit()
    }
    return pending
  }
  snapshot = { ...snapshot, loading: !snapshot.loaded, refreshing: manual }
  emit()
  pending = fetch('api/huohuo/notifications', { cache: 'no-store' })
    .then(async (response) => {
      if (!response.ok)
        throw Error(
          response.status === 401
            ? '登录已失效，请重新打开本机认证入口。'
            : response.status === 403
              ? '无权读取当前实例的提醒记录。'
              : '提醒记录暂时无法读取，请重试。',
        )
      const data = await response.json()
      if (!Array.isArray(data.items)) throw Error('提醒记录格式暂不可用。')
      snapshot = { ...snapshot, items: data.items, loaded: true, error: '' }
    })
    .catch((error) => {
      snapshot = { ...snapshot, error: error.message }
    })
    .finally(() => {
      pending = undefined
      snapshot = { ...snapshot, loading: false, refreshing: false }
      emit()
    })
  return pending
}
export function markActivitySeen(visible: readonly ActivityRecord[]) {
  const next = rememberActivity(readSeen(), visible)
  if (JSON.stringify(next) === JSON.stringify(seen)) return
  seen = next
  try {
    localStorage.setItem(key, JSON.stringify(seen))
  } catch {}
  emit()
}
function storage(event: StorageEvent) {
  if (event.key === key) {
    readSeen()
    emit()
  }
}
function focus() {
  void refreshActivity()
}
function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    readSeen()
    emit()
    void refreshActivity()
    timer = setInterval(focus, 30000)
    window.addEventListener('focus', focus)
    window.addEventListener('storage', storage)
  }
  return () => {
    listeners.delete(listener)
    if (!listeners.size) {
      clearInterval(timer)
      window.removeEventListener('focus', focus)
      window.removeEventListener('storage', storage)
    }
  }
}
export function useActivity() {
  return useSyncExternalStore(subscribe, () => snapshot)
}
