export interface ResearchResult {
  execution_id?: string
  summary?: string
  error?: string
  evidence_ids?: string[]
  judgements?: Record<string, { judgement: string; reason?: string; evidence_refs?: string[] }>
}
/** Browser read models; unknown fields never become generated facts. */
export interface Execution {
  execution_id: string
  question: string
  status: string
  revision: number
  mandate_revision?: number
  scope: { entity_id: string; exchange: string; operation: string }
  current_attempt: string | null
  created_at: number
  updated_at: number
  result: ResearchResult | null
}
export interface ExecutionList {
  executions: Execution[]
  limit: number
  has_more: boolean
}
export interface BusinessEvent {
  seq: number
  kind: string
  created_at: number
  data: Record<string, unknown>
}
export interface Evidence {
  evidence_id: string
  attempt_id: string
  status: string
  source: string
  observed_at?: string
  data_as_of?: string | null
  source_url?: string
  reason?: string
  limitations?: string[]
  raw?: { source?: string; complete?: boolean }
  scope?: {
    entity_id?: string
    operation?: string
    period?: string
    metric?: string
    exchange?: string
  }
  values?: {
    items?: Record<string, unknown>[]
    name?: string | null
    price?: string
    previous_close?: string
    change?: string
    change_percent?: string
    currency?: string
    metric?: string
    period?: string
    unit?: string
    records?: Record<string, unknown>[]
    profile?: Record<string, unknown>[]
  }
}
export const states: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  interrupted: '已中断',
  cancelled: '已取消',
}
export const eventNames: Record<string, string> = {
  'execution.created': '研究请求已接受',
  'attempt.claimed': '后台已领取任务',
  'runtime.accepted': '研究运行时已接收问题',
  'execution.succeeded': '结果已校验并保存',
  'execution.failed': '本次执行失败',
  'execution.interrupted': '执行租约到期，已标记中断',
  'execution.cancel': '用户已取消',
  'execution.retry': '用户已重试，重新排队',
}
export function label(table: Record<string, string>, key: string, fallback: string): string {
  return Object.hasOwn(table, key) ? table[key] : fallback
}
export function time(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const date = new Date(typeof value === 'number' ? value * 1000 : value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date)
}
export function safeSource(value?: string): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password
      ? url.href
      : undefined
  } catch {
    return undefined
  }
}
export function message(error: unknown): string {
  return error instanceof Error ? error.message : '暂时无法读取，请重试。'
}
/** Request data only from fixed same-origin endpoints; server owns all credentials. */
export async function read<T>(
  kind: 'executions' | 'execution' | 'events' | 'evidence',
  signal: AbortSignal,
  id?: string,
): Promise<T> {
  const response = await fetch(`api/huohuo/${kind}${id ? `?${new URLSearchParams({ id })}` : ''}`, {
    method: 'GET',
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  })
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as { error?: string } | null
    if (response.status === 502 && error?.error === 'response_too_large')
      throw new Error('记录内容超过页面读取上限，请通过本机 CLI 核对完整记录。其他区域仍可查看。')
    throw new Error(
      response.status === 401
        ? '登录已失效，请重新打开本机应用入口。'
        : response.status === 403
          ? '当前连接无权读取研究记录，请检查本机实例。'
          : response.status === 404
            ? '这项研究不存在或当前实例无法访问。'
            : response.status === 502
              ? '返回的数据暂时无法展示，请重试。'
              : '后台暂时不可用，请确认火火服务仍在运行，然后重试。',
    )
  }
  const data: unknown = await response.json()
  const object = (value: unknown): value is Record<string, unknown> =>
    !!value && typeof value === 'object' && !Array.isArray(value)
  const optionalText = (value: unknown) =>
    value === undefined || value === null || typeof value === 'string'
  const texts = (value: unknown) =>
    Array.isArray(value) && value.every((item) => typeof item === 'string')
  const result = (value: unknown) =>
    value === null ||
    (object(value) &&
      optionalText(value.summary) &&
      optionalText(value.error) &&
      (value.evidence_ids === undefined || texts(value.evidence_ids)))
  const execution = (value: unknown) =>
    object(value) &&
    typeof value.execution_id === 'string' &&
    typeof value.question === 'string' &&
    typeof value.status === 'string' &&
    object(value.scope) &&
    typeof value.scope.entity_id === 'string' &&
    typeof value.created_at === 'number' &&
    typeof value.updated_at === 'number' &&
    Number.isFinite(value.created_at) &&
    Number.isFinite(value.updated_at) &&
    typeof value.revision === 'number' &&
    optionalText(value.current_attempt) &&
    result(value.result)
  const valid =
    kind === 'executions'
      ? object(data) &&
        Array.isArray(data.executions) &&
        data.executions.every(execution) &&
        typeof data.has_more === 'boolean'
      : kind === 'execution'
        ? execution(data)
        : Array.isArray(data) &&
          data.every(
            (row) =>
              object(row) &&
              (kind === 'events'
                ? typeof row.seq === 'number' &&
                  typeof row.kind === 'string' &&
                  typeof row.created_at === 'number' &&
                  object(row.data)
                : typeof row.evidence_id === 'string' &&
                  typeof row.attempt_id === 'string' &&
                  typeof row.status === 'string' &&
                  typeof row.source === 'string' &&
                  [row.observed_at, row.data_as_of, row.source_url, row.reason].every(
                    optionalText,
                  ) &&
                  (row.limitations === undefined || texts(row.limitations)) &&
                  (row.values === undefined ||
                    (object(row.values) &&
                      [
                        'name',
                        'price',
                        'previous_close',
                        'change',
                        'change_percent',
                        'currency',
                      ].every((key) =>
                        optionalText(row.values && (row.values as Record<string, unknown>)[key]),
                      )))),
          )
  if (!valid) throw new Error('返回的数据格式无法识别，请重试。')
  return data as T
}
