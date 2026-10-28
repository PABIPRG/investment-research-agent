/** 受控回放模型：经真实 DSH 原生 loader 和工具执行，不替代业务服务。 */
import assert from 'node:assert/strict'
import { appendFile } from 'node:fs/promises'
import type { Context } from '@deepseek-ai/cordis'
import {
  LlmAdapter,
  ToolCallId,
  type GenerateOptions,
  type StreamChunk,
} from '@deepseek-ai/dsh-llm'
import { chatSkillNames } from '../product/chat/policy.js'
export const inject = ['llm']
export const scenarios = [
  ['R01', '你好', []],
  ['R02', '查看我的持仓与自选', ['huohuo-investment-facts', 'read_investment_facts']],
  ['R03', '查询持续委托', ['huohuo-mandates', 'list_mandates']],
  ['R04', '查询最近单次研究', ['huohuo-research-chat', 'list_research']],
  ['R05', '明确请求 600519 单次报价', ['huohuo-research-chat', 'submit_quote_research']],
  ['R06', '取消刚才的排队单次研究', ['huohuo-research-chat', 'list_research', 'cancel_research']],
  [
    'R07',
    '解析两个对象茅台和科士达，不授权委托',
    ['huohuo-research-chat', 'resolve_research_scope'],
  ],
  ['R08', '解析未知对象，不猜测', ['huohuo-research-chat', 'resolve_research_scope']],
  ['R09', '尝试禁止的 shell', ['huohuo-research-chat', 'bash']],
  ['R10', '尝试外部 Skill', ['external-skill']],
  ['R11', '伪造确认创建委托应被拒绝', ['huohuo-mandates', 'create_mandate']],
  ['R12', '查询不存在的单次研究', ['huohuo-research-chat', 'get_research']],
] as const
export function apply(ctx: Context) {
  assert.ok(process.env.HUOHUO_SKILLS_PROOF, '仅允许隔离回放加载')
  class Fixture extends LlmAdapter {
    async listModels(provider: string) {
      return [
        { provider, id: 'controlled', name: '受控 Skill 回放', inputModalities: ['text' as const] },
      ]
    }
    async resolveModel(provider: string, id: string) {
      return {
        provider,
        id,
        name: '受控 Skill 回放',
        inputModalities: ['text' as const],
        context: { contextWindow: 128000 },
        defaultMaxTokens: 2048,
      }
    }
    async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
      let text = '受控回放'
      let name = ''
      let args: any = {}
      if (options.purpose !== 'session-title') {
        const start = options.messages.findLastIndex(
          (m) => m.role === 'user' && m.source?.kind === 'user',
        )
        const input =
          start < 0
            ? ''
            : options.messages[start].content
                .filter((b) => b.type === 'text')
                .map((b) => b.text)
                .join('')
        const id = /^回放\s+(R\d{2}|U01)(?:[：:\s]|$)/.exec(input.trim())?.[1]
        if (!id || (id !== 'U01' && !scenarios.some((s) => s[0] === id))) {
          const notice =
            '【预览环境提示】这条问题没有执行研究。当前页面使用固定测试回放，未连接可自由对话的真实模型。你可以在“我的委托”中查看已有研究与资料；要继续自由提问，需要切换到已配置模型的正常产品实例。'
          yield { type: 'block-start', index: 0, blockType: 'text' }
          yield { type: 'text-delta', index: 0, text: notice }
          yield { type: 'block-end', index: 0, block: { type: 'text', text: notice } }
          yield { type: 'finish', reason: { kind: 'stop' } }
          return
        }
        const results = options.messages.slice(start + 1).filter((m) => m.role === 'tool')
        const step = results.length
        const value = (i = step - 1): any => {
          try {
            return JSON.parse(
              results[i]?.content
                .filter((b) => b.type === 'text')
                .map((b) => b.text)
                .join('') ?? 'null',
            )
          } catch {
            return undefined
          }
        }
        const whole = JSON.stringify(options.messages)
        if (step === 0) {
          assert.ok(whole.includes('<available_skills>'), '真实 DSH Skill 目录必须进入请求')
          assert.ok(chatSkillNames.every((n) => whole.includes(n)))
          assert.ok(!whole.includes('本实例逐个注册 48 个研究工具'), '首次请求不得塞入方法正文')
        }
        const sequence: readonly string[] =
          id === 'U01'
            ? [
                'huohuo-research-chat',
                'huohuo-mandates',
                'resolve_research_scope',
                'confirm_research_entities',
                'create_mandate',
              ]
            : scenarios.find((s) => s[0] === id)![2]
        const action = sequence[step]
        if (step > 0 && sequence[step - 1].startsWith('huohuo-')) {
          assert.notEqual(results.at(-1)!.isError, true)
          assert.ok(
            results
              .at(-1)!
              .content.some((b) => b.type === 'text' && b.text.includes('<skill_content')),
            '必须由原生 loader 返回正文',
          )
        }
        if (action?.startsWith('huohuo-') || action === 'external-skill') {
          name = 'skill'
          args = { name: action }
        } else if (action) {
          name = action
          if (action === 'submit_quote_research')
            args = { code: '600519', question: '明确受控报价回放；合成数据' }
          if (action === 'cancel_research') {
            const job = value().data.executions[0]
            args = { execution_id: job.execution_id, expected_revision: job.revision }
          }
          if (action === 'resolve_research_scope')
            args =
              id === 'R07'
                ? { query: '研究茅台和科士达', mention_texts: ['茅台', '科士达'] }
                : {
                    query: id === 'R08' ? '不存在的合成对象XYZ' : '600519 财务摘要',
                    mention_texts: [id === 'R08' ? '不存在的合成对象XYZ' : '600519'],
                  }
          if (action === 'get_research')
            args = { execution_id: '00000000-0000-4000-8000-000000000000' }
          if (action === 'confirm_research_entities')
            args = { snapshot_id: value().data.snapshot_id, version: value().data.version }
          if (action === 'create_mandate') {
            const c = value()?.confirmations?.[0]
            if (id === 'U01' && !c) {
              name = ''
              text = '你尚未确认对象，未创建委托。可以重新发起回放 U01。'
            } else
              args = {
                confirmation_id: c?.confirmation_id ?? 'forged',
                goal: '合成半年报营业总收入研究',
                scope: {
                  entity_id: c?.execution_entity_id ?? 'SEC:CN:A:600519',
                  exchange: c?.exchange ?? 'SSE',
                  operation: 'financial_summary',
                  period: '20260630',
                  metric: '营业总收入',
                  basis: 'source_abstract',
                },
                contact_note: '仅在产品内查看，不授权外部通知',
              }
          }
        } else {
          if (['R09', 'R10'].includes(id)) assert.equal(results.at(-1)?.isError, true)
          if (id === 'R11') assert.equal(value()?.ok, false)
          if (id === 'R12')
            assert.ok(
              results.at(-1)?.isError === true || value()?.ok === false,
              '不存在的任务必须明确失败',
            )
          if (id === 'R05') assert.equal(value()?.data.status, 'queued')
          if (id === 'R06') assert.equal(value()?.data.status, 'cancelled')
          if (id === 'R07') assert.equal(value()?.data.mentions.length, 2)
          if (id === 'U01') assert.equal(value()?.ok, true)
          text =
            id === 'U01'
              ? '已保存合成验收委托。请到委托查询查看真实进展与证据；这不是实际投资研究。'
              : `${id} 受控回放已核对工具回执。${['R09', 'R10', 'R11', 'R12'].includes(id) ? '请求被拒绝，没有新增业务写入。' : '未授权外部通知。'}`
        }
        await appendFile(
          process.env.HUOHUO_SKILLS_PROOF!,
          JSON.stringify({
            case: id,
            step,
            session: options.sessionId,
            call: name || null,
            result: results.at(-1) ?? null,
            system_bytes: Buffer.byteLength(
              JSON.stringify(options.messages.filter((m) => m.role === 'system')),
            ),
            catalog_bytes: Buffer.byteLength(
              JSON.stringify(
                options.messages.filter(
                  (m) =>
                    m.role === 'user' &&
                    m.content.some(
                      (b) => b.type === 'text' && b.text.includes('<available_skills>'),
                    ),
                ),
              ),
            ),
            loaded_skill_bytes: Buffer.byteLength(
              JSON.stringify(
                options.messages.filter(
                  (m) =>
                    m.role === 'tool' &&
                    m.content.some((b) => b.type === 'text' && b.text.includes('<skill_content')),
                ),
              ),
            ),
            schema_bytes: Buffer.byteLength(JSON.stringify(options.tools)),
            status: name ? 'stepping' : 'completed',
          }) + '\n',
          { mode: 0o600 },
        )
      }
      if (name) {
        const id = ToolCallId(`controlled-${crypto.randomUUID()}`),
          argumentsText = JSON.stringify(args)
        yield { type: 'block-start', index: 0, blockType: 'tool-call' }
        yield { type: 'tool-call-delta', index: 0, id, name, argumentsDelta: argumentsText }
        yield {
          type: 'block-end',
          index: 0,
          block: { type: 'tool-call', id, name, arguments: argumentsText },
        }
        yield { type: 'finish', reason: { kind: 'tool-calls' } }
        return
      }
      yield { type: 'block-start', index: 0, blockType: 'text' }
      yield { type: 'text-delta', index: 0, text }
      yield { type: 'block-end', index: 0, block: { type: 'text', text } }
      yield { type: 'finish', reason: { kind: 'stop' } }
    }
  }
  ctx.llm.registerAdapter(['huohuo-skills-fixture'], new Fixture())
}
