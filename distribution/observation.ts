/** 只提取 DSH 事件的必要事实，不记录提示词、工具参数、完整结果或环境凭据。 */
export function activityObservation(event: any): Record<string, unknown> | undefined {
  const data = event.data ?? {}
  if (event.type === 'agent/inbox/spliced') return { kind: event.type, message_ids: data.inserted?.map((item: any) => item.id) ?? [] }
  if (event.type === 'system/message') return { kind: event.type, skill_visible: JSON.stringify(data.message).includes('HUOHUO_BOUNDED_QUOTE_V1') }
  if (event.type === 'request/header') return { kind: event.type, provider: data.header?.config?.provider, model: data.header?.config?.model,
    tools: data.header?.tools?.map((item: any) => item.name) ?? [] }
  if (event.type === 'tool/call') return { kind: event.type, call_id: data.callId, tool: data.name }
  if (event.type === 'tool/result') {
    let evidence: any
    try { evidence = JSON.parse(data.message.content.filter((item: any) => item.type === 'text').map((item: any) => item.text).join('')) } catch { /* 错误文字不进入观察摘要。 */ }
    return { kind: event.type, call_id: data.message?.toolCallId, is_error: data.message?.isError === true,
      ...(evidence?.evidence_id ? { evidence_id: evidence.evidence_id, evidence_status: evidence.status } : {}) }
  }
  if (event.type === 'turn/end') return { kind: event.type, reason: data.reason?.kind }
  return undefined
}

export interface RuntimeObservation {
  kind: string; observed_at: string; execution_id: string; attempt_id: string
  [key: string]: unknown
}
export type RuntimeObserver = (event: RuntimeObservation) => void
