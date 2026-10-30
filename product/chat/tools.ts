import { createTransferTools, transferToolNames } from './transfer-tools.js'
import { createIndustryChainTools, industryChainToolNames } from './industry-chain-tools.js'
import type { Context } from '@deepseek-ai/cordis'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import * as skillFilesystem from '@deepseek-ai/dsh-skill-filesystem'
import { fileURLToPath } from 'node:url'
import { chatInvariants } from './policy.js'
import '@deepseek-ai/dsh-system-prompt'
import { createHash } from 'node:crypto'

import { createEntityConfirmationTool, nativeEntityQuestion, entityToolName } from './entity-tools.js'
import { createResearchTools, researchToolNames } from '../tools/research-tools.js'
import { createStrategyTools, strategyToolNames, type StrategyQuestion } from './strategy-tools.js'
import { createInvestmentTools, investmentToolNames } from './investment-tools.js'
import { createNotificationTools, notificationToolNames } from './notification-tools.js'
import { createNavigationTools, navigationToolNames } from './navigation-tools.js'
import { createMarketTools, marketToolNames } from './market-tools.js'
import { createMandateTools, mandateToolNames } from './mandate-tools.js'
import { createRiskTools, riskToolNames } from './risk-tools.js'
import {createPersonalizationTools,personalizationToolNames} from './personalization-tools.js'
import {createPositionRiskTools,positionRiskToolNames} from './position-risk-tools.js'
import {createResearchReviewTools,researchReviewToolNames} from './research-review-tools.js'
import { createDeliverableTools, deliverableToolNames } from './deliverable-tools.js'
import { deliveryRecorder } from './deliverable-events.js'

export const chatToolNames = ['submit_quote_research', 'list_research', 'get_research', 'research_events',
  'research_evidence', 'cancel_research', 'retry_research', ...mandateToolNames, ...researchToolNames, ...researchReviewToolNames, ...investmentToolNames, ...riskToolNames, ...personalizationToolNames, ...positionRiskToolNames, ...notificationToolNames, ...navigationToolNames, ...strategyToolNames, ...marketToolNames, ...industryChainToolNames, ...transferToolNames, ...deliverableToolNames]
export const nativeChatToolNames = ['ask_user_question', 'skill']
export const allowedChatToolNames = [...chatToolNames, ...nativeChatToolNames, entityToolName]
export const inject = ['tools', 'skills', 'systemPrompt', 'sessionProjections']
const idSchema = { type: 'string', description: 'API 返回的 execution_id' }
const revisionSchema = { type: 'integer', minimum: 1, description: '最近查询得到的 revision' }

function exact(value: unknown, keys: string[]): Record<string, any> {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).sort().join(',') !== [...keys].sort().join(',')) throw new Error('参数缺失或包含未允许字段')
  return value as Record<string, any>
}

export function createChatTools(address: string, token: string, ask?: StrategyQuestion, created?: Parameters<typeof createDeliverableTools>[2], webOrigin?: Parameters<typeof createNavigationTools>[2]): ToolDefinition[] {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/'
    || base.username || base.password || base.search || base.hash || !token) throw new Error('聊天 API 配置无效')
  const specs: [string, string, Record<string, unknown>][] = [
    [chatToolNames[0], '按用户明确要求提交一项沪深 A 股单次报价研究。仅返回已接受回执；不是完成。需明确六位证券代码。',
      { code: { type: 'string', pattern: '^[0-9]{6}$' }, question: { type: 'string', minLength: 1, maxLength: 4000 } }],
    [chatToolNames[1], '查询当前实例最近 50 项任务，重开会话后也可找回；不代表全部历史。', {}],
    [chatToolNames[2], '查询任务的真实状态、revision 和结果；不可从对话推断完成。', { execution_id: idSchema }],
    [chatToolNames[3], '查询任务事件，区分排队、领取、DSH 收件和结果入库。', { execution_id: idSchema }],
    [chatToolNames[4], '查询留存证据及时间、来源和 attempt；当前结果引用的 evidence_ids 才属于当前结果。', { execution_id: idSchema }],
    [chatToolNames[5], '用户明确要求后取消 queued/running 任务；先查询 revision。取消阻断迟到提交，不保证外部请求撤回。',
      { execution_id: idSchema, expected_revision: revisionSchema }],
    [chatToolNames[6], '仅在用户明确要求重试时，对 failed/interrupted 任务创建新尝试；先查询 revision，禁止自动重试。',
      { execution_id: idSchema, expected_revision: revisionSchema }],
  ]
  return [...specs.map<ToolDefinition>(([name, description, properties]) => ({
    name, description, parameters: { type: 'object', properties, required: Object.keys(properties), additionalProperties: false },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    timeoutMs: 20_000,
    async execute(input, exec) {
      const args = exact(input, Object.keys(properties))
      const session = exec.agent?.session.id
      if (!session || !exec.callId) throw new Error('缺少可信会话与工具调用身份')
      const requestKey = 'chat:' + createHash('sha256').update(JSON.stringify([session, exec.callId, name])).digest('hex')
      let path = '/executions'; let body: unknown
      if (name === 'submit_quote_research') {
        if (typeof args.code !== 'string' || !/^\d{6}$/.test(args.code)) throw new Error('请提供六位沪深 A 股代码')
        const exchange = /^(600|601|603|605|688|689)/.test(args.code) ? 'SSE'
          : /^(000|001|002|003|300|301)/.test(args.code) ? 'SZSE' : null
        if (!exchange) throw new Error('当前只支持沪深 A 股代码，不支持指数或其他市场')
        if (typeof args.question !== 'string' || !args.question.trim() || args.question.length > 4000) throw new Error('问题须为 1–4000 字的文本')
        body = { request_key: requestKey, scope: { entity_id: `SEC:CN:A:${args.code}`, exchange, operation: 'quote_snapshot' }, question: args.question }
      } else if (name !== 'list_research') {
        if (typeof args.execution_id !== 'string' || !/^[0-9a-f-]{36}$/i.test(args.execution_id)) throw new Error('任务 ID 无效，请先查询任务列表')
        path += '/' + args.execution_id
        if (name === 'research_events') path += '/events'
        if (name === 'research_evidence') path += '/evidence'
        if (name === 'cancel_research' || name === 'retry_research') {
          if (!Number.isSafeInteger(args.expected_revision) || args.expected_revision < 1) throw new Error('请先查询任务的有效 revision')
          path += name === 'cancel_research' ? '/cancel' : '/retry'
          body = { request_key: requestKey, expected_revision: args.expected_revision }
        }
      }
      try {
        const response = await fetch(new URL(path, base), { method: body === undefined ? 'GET' : 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: AbortSignal.any([exec.signal, AbortSignal.timeout(15_000)]), redirect: 'error' })
        const result = await response.json() as any
        if (!response.ok) return { ok: false, http_status: response.status, error: result.error, detail: result.detail,
          guidance: '冲突或失败不等于成功。查询最新状态；不得自动重新提交或重试研究。' }
        return { ok: true, data: result, ...(body ? { request_key: requestKey } : {}) }
      } catch {
        return { ok: false, error: body ? 'submission_unknown' : 'backend_unavailable', request_key: requestKey,
          guidance: '后台连接中断。写操作可能已被接受；先查询最近任务核对，不要创建另一项重复研究。' }
      }
    },
  })), ...createMandateTools(address, token, ask), ...createResearchTools(address, token), ...createResearchReviewTools(address, token), ...createInvestmentTools(address, token, ask), ...createRiskTools(address, token, ask), ...createPersonalizationTools(address, token, ask), ...createPositionRiskTools(address, token), ...createNotificationTools(address, token, ask), ...createNavigationTools(address, token, webOrigin), ...createStrategyTools(address, token, ask), ...createMarketTools(address, token), ...createIndustryChainTools(address, token, ask), ...createTransferTools(address, token, ask), ...createDeliverableTools(address, token, created)]
    .sort((a, b) => chatToolNames.indexOf(a.name) - chatToolNames.indexOf(b.name))
}

export async function apply(ctx: Context): Promise<void> {
  for (const tool of createChatTools(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '', nativeEntityQuestion(ctx), deliveryRecorder(ctx), () => {
    // DSH owns the advertised publicUrl and local listener fallback. Read it lazily after assembly.
    const web = ctx.get('webApp' as any) as { getAdvertisedUrl(): string } | undefined
    return web?.getAdvertisedUrl() ?? process.env.HUOHUO_CHAT_WEB_ORIGIN
  })) ctx.tools.register(tool)
  ctx.tools.register(createEntityConfirmationTool(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '', nativeEntityQuestion(ctx)))
  ctx.plugin(skillFilesystem, { providerName: 'huohuo-bundled', includeDefaultRoots: false,
    bundledSkillDir: fileURLToPath(new URL('../../../product/skills/chat/', import.meta.url)), watch: false })
  ctx.systemPrompt.section({ name: 'huohuo:invariants', order: 100, text: chatInvariants, interpolate: false })
}
