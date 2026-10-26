// 无模型装配检查插件，仅由隔离测试通过 --patch 显式装配。
import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import type { Context } from '@deepseek-ai/cordis'
import { ToolCallId } from '@deepseek-ai/dsh-llm'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { allowedChatToolNames } from '../product/chat/tools.js'
export const inject = ['agents', 'tools', 'agentPresets', 'skills', 'systemPrompt', 'agentDefaultModel']
export function apply(ctx: Context): void {
  const host = ctx as any
  // 不在 Loader activation 内等待 preset settlement。
  setTimeout(() => { void audit().catch(error => writeFile(process.env.HUOHUO_CHAT_AUDIT!, JSON.stringify({ status: 'failed', error: String(error) }))) }, 0)
  async function audit() {
    const roster = await host.agentPresets.list()
    assert.deepEqual(roster.map((p: any) => p.id), ['huohuo'])
    assert.equal(host.agentDefaultModel.currentSelection().model, 'uat-model-selection')
    const handles = []
    try {
      for (let i = 0; i < 2; i++) handles.push(await ctx.agents.create({ sessionId: randomUUID() as any,
        meta: { cwd: process.cwd(), agentPreset: 'huohuo' }, agentOptions: { provider: 'deepseek-official', model: 'deepseek-flash' },
        setup: async agentCtx => { await host.agentPresets.mount(agentCtx, 'huohuo') } }))
      const [a, b] = handles.map(h => h.agent)
      const names = a.ctx.tools.schemas(a).map((t: any) => t.name)
      assert.deepEqual([...names].sort(), [...allowedChatToolNames].sort())
      assert.ok(await ctx.skills.get('huohuo-research-chat', { scope: a }))
      const prompt = await ctx.systemPrompt.assemble({ agent: a, scope: a })
      assert.ok(prompt.sections.some(section => section.name === 'huohuo:invariants' && section.text.includes('程序回执')))
      let entered = false
      const sentinel: ToolDefinition = { name: 'huohuo_chat_test_sentinel', description: '测试哨兵', parameters: { type: 'object' },
        output: { schema: { type: 'string' }, render: () => [{ type: 'text' as const, text: 'unexpected' }] },
        async execute() { entered = true; return 'unexpected' } }
      const execute = (agent: typeof a, name: string, args: any, id: string = randomUUID()) => agent.ctx.tools.execute({
        callId: ToolCallId(id), agent, name, arguments: args, signal: new AbortController().signal })
      let remove = ctx.tools.register(sentinel)
      assert.equal((await ctx.tools.execute({ name: sentinel.name, callId: ToolCallId('root'), arguments: {}, signal: new AbortController().signal })).isError, true)
      remove(); remove = a.ctx.tools.register(sentinel)
      assert.equal((await execute(a, sentinel.name, {})).isError, true); remove(); assert.equal(entered, false)
      for (const name of ['bash', 'write', 'web_fetch', 'subagent', 'run_code']) assert.equal((await execute(a, name, {})).isError, true)
      const data = (result: any) => { assert.equal(result.isError, false); return JSON.parse(result.content.filter((x: any) => x.type === 'text').map((x: any) => x.text).join('')) }
      const args = { code: '600519', question: '无模型装配测试，不采集行情' }
      const first = data(await execute(a, 'submit_quote_research', args, 'same-call')).data
      assert.equal(first.status, 'queued')
      assert.equal(data(await execute(a, 'submit_quote_research', args, 'same-call')).data.execution_id, first.execution_id)
      const second = data(await execute(b, 'submit_quote_research', args, 'same-call')).data
      assert.notEqual(second.execution_id, first.execution_id)
      assert.equal(data(await execute(a, 'cancel_research', { execution_id: first.execution_id, expected_revision: first.revision })).data.status, 'cancelled')
      assert.equal(data(await execute(b, 'list_research', {})).data.executions.length, 2)
      await writeFile(process.env.HUOHUO_CHAT_AUDIT!, JSON.stringify({ status: 'passed', preset: 'huohuo', tools: names,
        root_guard: true, agent_guard: true, invariants_in_prompt: true, model_override_preserved: true,
        cross_session_idempotency: true, actual_api: true, model_called: false, market_called: false }, null, 2))
    } finally { for (const handle of handles) await handle.dispose() }
  }
}
