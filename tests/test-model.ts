// 仅用于无密钥装配验证；此适配器不是产品模型，也不替代真实工具/API/SQLite。
import { LlmAdapter, ToolCallId, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'
import type { Context } from '@deepseek-ai/cordis'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import assert from 'node:assert/strict'

export const inject = ['llm', 'tools']
const blocked = ['bash', 'write', 'web_fetch', 'subagent', 'run_code']

export function apply(ctx: Context): void {
  const proof = { agent_scope_guard: false, root_guard: false, blocked_calls: [] as string[], skill_loaded: false, tool_names: [] as string[] }
  let entered = 0
  const sentinel: ToolDefinition = { name: 'huohuo_test_sentinel', description: '拒绝执行的测试哨兵', parameters: { type: 'object' },
    output: { schema: { type: 'string' }, render: (_, value) => [{ type: 'text', text: String(value) }] },
    async execute() { entered++; return 'unexpected' } }
  ctx.on('agent/created', async ({ agent }) => {
    const remove = agent.ctx.tools.register(sentinel)
    try {
      const result = await ctx.tools.execute({ callId: ToolCallId('scope-guard'), name: sentinel.name, arguments: {}, agent, signal: new AbortController().signal })
      assert.equal(result.isError, true)
      assert.equal(entered, 0)
      proof.agent_scope_guard = true
    } finally { remove() }
    return undefined
  })
  class Fixture extends LlmAdapter {
    async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
      options.signal?.throwIfAborted()
      proof.tool_names = (options.tools ?? []).map(tool => tool.name)
      assert.deepEqual(proof.tool_names, ['read_security_snapshot'])
      assert.ok(JSON.stringify(options.messages).includes('HUOHUO_BOUNDED_QUOTE_V1'))
      proof.skill_loaded = true
      const remove = ctx.tools.register(sentinel)
      try {
        const result = await ctx.tools.execute({ callId: ToolCallId('root-guard'), name: sentinel.name, arguments: {}, signal: new AbortController().signal })
        assert.equal(result.isError, true)
        assert.equal(entered, 0)
        proof.root_guard = true
      } finally { remove() }
      const toolMessages = options.messages.filter(message => message.role === 'tool')
      const blockedForRun = options.model === 'demo-fixture' ? [] : blocked
      for (const message of toolMessages) {
        if (String(message.toolCallId).startsWith('blocked-')) {
          assert.equal(message.isError, true)
          const name = String(message.toolCallId).slice(8)
          if (!proof.blocked_calls.includes(name)) proof.blocked_calls.push(name)
        }
      }
      if (toolMessages.length < blockedForRun.length + 1) {
        const index = toolMessages.length
        const name = blockedForRun[index] ?? 'read_security_snapshot'
        const id = ToolCallId(index < blockedForRun.length ? 'blocked-' + name : 'real-quote')
        yield { type: 'block-start', index: 0, blockType: 'tool-call' }
        yield { type: 'tool-call-delta', index: 0, id, name, argumentsDelta: '{}' }
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id, name, arguments: '{}' } }
        yield { type: 'finish', reason: { kind: 'tool-calls' } }
        return
      }
      const message = toolMessages.at(-1)!
      assert.notEqual(message.isError, true)
      const evidence = JSON.parse(message.content.filter(block => block.type === 'text').map(block => block.text).join(''))
      const text = JSON.stringify(evidence.status === 'ok' ? {
        status: 'succeeded', execution_id: evidence.execution_id, scope: evidence.scope, evidence_ids: [evidence.evidence_id],
        summary: '装配测试：真实工具回执中的价格=' + evidence.values.price + '，变化=' + evidence.values.change_percent + '%。仅证明单次快照链路。',
      } : { status: 'failed', error: '真实工具没有取得可用证据：' + evidence.status })
      await writeFile(join(dirname(process.env.HUOHUO_RUNTIME_ACK_PATH!), 'test-proof.json'), JSON.stringify(proof), { mode: 0o600 })
      yield { type: 'block-start', index: 0, blockType: 'text' }
      yield { type: 'text-delta', index: 0, text }
      yield { type: 'block-end', index: 0, block: { type: 'text', text } }
      yield { type: 'finish', reason: { kind: options.model === 'truncated-fixture' ? 'max-tokens' : 'stop' } }
    }
  }
  ctx.llm.registerAdapter(['huohuo-test'], new Fixture())
}
