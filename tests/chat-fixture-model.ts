// 隔离浏览器验收专用，产品 Bundle 不装载本插件。
import assert from 'node:assert/strict'
import { appendFile } from 'node:fs/promises'
import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-agent'
import { LlmAdapter, ToolCallId, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'
import { allowedChatToolNames } from '../product/chat/tools.js'
export const inject = ['llm', 'agents', 'tools']
const provider = 'huohuo-chat-uat'
const model = 'deterministic-chat'
export function apply(ctx: Context): void {
  const proof = process.env.HUOHUO_CHAT_FIXTURE_PROOF
  assert.ok(proof, '本插件仅供隔离验收')
  class Fixture extends LlmAdapter {
    async listModels(route: string) { return [{ provider: route, id: model, name: '隔离聊天验收模型', inputModalities: ['text' as const] }] }
    async resolveModel(route: string, id: string) {
      assert.equal(route, provider); assert.equal(id, model)
      return { provider: route, id, name: '隔离聊天验收模型', inputModalities: ['text' as const], context: { contextWindow: 128000 }, defaultMaxTokens: 1024 }
    }
    async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
      options.signal?.throwIfAborted()
      assert.equal(options.provider, provider); assert.equal(options.model, model)
      let text = '火火验收对话'
      if (options.purpose !== 'session-title') {
        assert.equal(options.purpose, undefined); assert.ok(options.sessionId)
        const agent = ctx.agents.get(options.sessionId)
        assert.ok(agent); assert.equal(agent.session.header.agentPreset, 'huohuo')
        const names = (options.tools ?? []).map(tool => tool.name).sort()
        assert.deepEqual(names, [...allowedChatToolNames].sort())
        assert.ok(JSON.stringify(options.messages).includes('程序回执'))
        // A forbidden request must be rejected before any executor is reached.
        let entered = false
        const remove = agent.ctx.tools.register({ name: 'huohuo_shell_sentinel', description: '验收哨兵', parameters: { type: 'object' },
          output: { schema: { type: 'string' }, render: () => [{ type: 'text' as const, text: 'unexpected' }] }, async execute() { entered = true; return 'unexpected' } })
        try {
          const result = await agent.ctx.tools.execute({ callId: ToolCallId('shell-sentinel'), agent, name: 'huohuo_shell_sentinel', arguments: {}, signal: new AbortController().signal })
          assert.equal(result.isError, true); assert.equal(entered, false)
        } finally { remove() }
        // DSH also appends user-role runtime context; select the marked UAT request.
        const message = [...options.messages].reverse().find(message => message.role === 'user' && message.content.some(block => block.type === 'text' && block.text.includes('验收编号')))
        assert.ok(message)
        const input = message.content.filter(block => block.type === 'text').map(block => block.text).join('')
        text = `火火验收回复：${input}`
        await appendFile(proof!, JSON.stringify({ session_id: options.sessionId, preset: agent.session.header.agentPreset, tools: names,
          input, output: text, guard: true, actual_provider_called: false, market_called: false }) + '\n', { mode: 0o600 })
      }
      yield { type: 'block-start', index: 0, blockType: 'text' }
      yield { type: 'text-delta', index: 0, text }
      yield { type: 'block-end', index: 0, block: { type: 'text', text } }
      yield { type: 'finish', reason: { kind: 'stop' } }
    }
  }
  ctx.llm.registerAdapter([provider], new Fixture())
}
