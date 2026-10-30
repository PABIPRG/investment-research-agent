import { useEffect, useRef, useState } from 'react'
import { useSnapshot } from '../shared/useSnapshot.js'
import type { MandateView } from './model.js'
import { semanticCondition, type ContactRule } from './ContactRuleEditor.js'
async function api(path: string, signal?: AbortSignal, body?: unknown) {
  const response = await fetch(`api/huohuo/${path}`, {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
    cache: 'no-store',
  })
  const data = await response.json()
  if (!response.ok)
    throw Object.assign(
      new Error(
        response.status === 403
          ? '无权访问此实例。请重新连接。'
          : data.detail || '读取失败，请稍后重试。',
      ),
      { http_status: response.status },
    )
  return data
}
export function useMandates() {
  const [selected, setSelected] = useState<string | undefined>(() => {
      try {
        return JSON.parse(sessionStorage.getItem('huohuo-return') || '{}').mandate
      } catch {
        return undefined
      }
    }),
    [refresh, setRefresh] = useState(0),
    [trigger, setTrigger] = useState('all')
  const [busy, setBusy] = useState(false),
    [feedback, setFeedback] = useState('')
  const [filter, setFilter] = useState('all'),
    [editing, setEditing] = useState(false),
    [goal, setGoal] = useState(''),
    [note, setNote] = useState('')
  const [contactChannels, setContactChannels] = useState<string[]>(['app'])
  const [reminder, setReminder] = useState(false),
    [reminderTime, setReminderTime] = useState('09:00')
  const [contactRule, setContactRule] = useState<ContactRule>({
    mode: 'condition',
    condition: semanticCondition,
  })
  const [operation, setOperation] = useState('financial_summary')
  const [briefPeriod, setBriefPeriod] = useState('post')
  const pending = useRef<{ fingerprint: string; key: string }>()
  const heading = useRef<HTMLHeadingElement>(null)
  const snapshot = useSnapshot<{ items: MandateView[] }>(
    `mandates:${refresh}`,
    (signal) => api('mandates', signal),
    {
      paused: busy || editing,
      pollMs: (data) =>
        data.items.some((x) => x.executions.some((e) => ['queued', 'running'].includes(e.status)))
          ? 3000
          : 60000,
    },
  )
  const items = snapshot.data?.items ?? [],
    loading = snapshot.loading,
    error = snapshot.error,
    loaded = snapshot.data !== undefined
  const setItems = (update: (old: MandateView[]) => MandateView[]) =>
    snapshot.replace((old) => (old ? { ...old, items: update(old.items) } : old))
  const located = useRef('')
  useEffect(() => {
    const open = (event: Event) => {
      setSelected((event as CustomEvent<string>).detail)
      setRefresh((n) => n + 1)
    }
    window.addEventListener('huohuo-mandate-view', open)
    return () => window.removeEventListener('huohuo-mandate-view', open)
  }, [])
  const returnDecision = (() => {
    try {
      return JSON.parse(sessionStorage.getItem('huohuo-return') || '{}').decision
    } catch {
      return undefined
    }
  })()
  const returnExecution = (() => {
    try {
      return JSON.parse(sessionStorage.getItem('huohuo-return') || '{}').execution as
        | string
        | undefined
    } catch {
      return undefined
    }
  })()
  const current = items.find((x) => x.mandate.mandate_id === selected)
  useEffect(() => {
    const key = `${selected}:${returnDecision}:${returnExecution}`
    if (current && (returnDecision || returnExecution) && located.current !== key) {
      const el = document.getElementById(returnDecision || `execution-${returnExecution}`)
      if (el) {
        located.current = key
        el.scrollIntoView({ block: 'center' })
        el.focus()
      }
    }
  }, [current, returnDecision, returnExecution])
  useEffect(() => {
    setEditing(false)
    setFeedback('')
    heading.current?.focus()
  }, [selected])
  const command = async (action: string) => {
    if (!current) return

    const payload = {
      action,
      mandate_id: selected,
      expected_revision: current.mandate.current_revision,
      expected_generation: current.generation,
      ...(action === 'revise'
        ? {
            goal,
            scope:
              operation === current.revision.scope.operation && operation !== 'market_brief'
                ? current.revision.scope
                : {
                    entity_id: current.revision.scope.entity_id,
                    exchange: current.revision.scope.exchange,
                    operation,
                    ...(operation === 'market_brief' ? { period: briefPeriod } : {}),
                  },
            contact_note: note,
            contact_rule: contactRule,
            contact_channels: contactChannels,
          }
        : {}),
    }
    const fingerprint = JSON.stringify(payload)
    if (pending.current?.fingerprint !== fingerprint)
      pending.current = { fingerprint, key: crypto.randomUUID() }
    snapshot.invalidate()
    setBusy(true)
    setFeedback('')
    try {
      const updated = await api('mandate-command', undefined, {
        ...payload,
        request_key: pending.current.key,
      })
      setItems((old) => old.map((x) => (x.mandate.mandate_id === selected ? updated : x)))
      setEditing(false)
      setFeedback('已保存，当前状态以详情为准。')
      pending.current = undefined
    } catch (e) {
      setFeedback((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return {
    items,
    loaded,
    refreshing: snapshot.refreshing,
    refreshNow: snapshot.refresh,
    trigger,
    setTrigger,
    selected,
    setSelected,
    refresh,
    setRefresh,
    loading,
    error,
    busy,
    feedback,
    filter,
    setFilter,
    editing,
    setEditing,
    goal,
    setGoal,
    note,
    setNote,
    contactRule,
    setContactRule,
    operation,
    setOperation,
    briefPeriod,
    setBriefPeriod,
    contactChannels,
    setContactChannels,
    reminder,
    setReminder,
    reminderTime,
    setReminderTime,
    heading,
    current,
    returnDecision,
    returnExecution,
    command,
  }
}
export type MandateController = ReturnType<typeof useMandates>
