import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { researchToolCatalog } from './research-tools.generated.js'
// 私有台账统一经投资事实工具读取，撤下无法完成授权的旧入口。
export const retiredResearchToolNames = ['portfolio_lookup', 'portfolio_risk_analysis', 'watchlist_lookup', 'event_monitor_setup']
export const activeResearchTools = researchToolCatalog.filter(t => !retiredResearchToolNames.includes(t.name))
export const researchToolNames = activeResearchTools.map(t => t.name)
export function createResearchTools(address: string, token: string): ToolDefinition[] {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/'
      || base.username || base.password || base.search || base.hash || !token) throw new Error('研究工具 API 配置无效')
  return activeResearchTools.map(spec => ({
    name: spec.name, description: spec.description, parameters: spec.parameters,
    timeoutMs: 120_000,
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    async execute(input, exec) {
      const session = exec.agent?.session.id
      if (!session || !exec.callId) throw new Error('缺少可信会话与工具调用身份')
      const schema = spec.parameters
      if (!input || typeof input !== 'object' || Array.isArray(input)
          || Object.keys(input).some(k => !(k in schema.properties))
          || schema.required.some(k => !(k in input))) throw new Error('参数缺失或包含未允许字段')
      try {
        const response = await fetch(new URL('/research-tools/run', base), {
          method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: session, call_id: exec.callId, tool_id: spec.name, arguments: input }),
          signal: AbortSignal.any([exec.signal, AbortSignal.timeout(115_000)]),
        })
        const result = await response.json() as Record<string, unknown>
        if (!response.ok) return { status: 'error', http_status: response.status, ...result }
        return result
      } catch {
        return { status: 'unavailable', error: '研究工具连接中断或超时，本次调用结果未确认。不要将其当作无数据或自动重试。' }
      }
    },
  }))
}
