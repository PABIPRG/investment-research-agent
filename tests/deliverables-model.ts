/** 固定受控模型，仅用于 PAB-67 独立实例，不配置真实 provider。 */
import assert from 'node:assert/strict'
import { LlmAdapter, ToolCallId, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'
import type { Context } from '@deepseek-ai/cordis'
export const inject = ['llm']
export function apply(ctx: Context) {
  assert.ok(process.env.HUOHUO_SKILLS_PROOF, '仅允许隔离验收')
  class Fixture extends LlmAdapter {
    async listModels(provider: string) { return [{ provider, id: 'controlled', name: '成果受控验收', inputModalities: ['text' as const] }] }
    async resolveModel(provider: string, id: string) { return { provider, id, name: '成果受控验收', inputModalities: ['text' as const], context: { contextWindow: 128000 }, defaultMaxTokens: 2048 } }
    async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
      let name = '', args: any = {}, text = '成果受控验收'
      if (options.purpose !== 'session-title') {
        const start = options.messages.findLastIndex(m => m.role === 'user' && m.source?.kind === 'user')
        const input = start < 0 ? '' : JSON.stringify(options.messages[start].content)
        const format = /交付回放\s+(CSV|JSON|Excel)/i.exec(input)?.[1].toLowerCase()
        const results = options.messages.slice(start + 1).filter(m => m.role === 'tool')
        const previous = () => JSON.parse(results.at(-1)!.content.filter(b => b.type === 'text').map(b => b.text).join(''))
        if (!format) text = '受控验收：仅接受“交付回放 CSV / JSON / Excel”，未连接真实模型。'
        else if (results.length === 0) { name = 'skill'; args = { name: 'huohuo-deliverables' } }
        else if (results.length === 1) { name = 'market_overview_lookup' }
        else if (results.length === 2) {
          const source = previous()
          assert.equal(source.status, 'ok')
          name = 'create_research_file'
          args = { format: format === 'excel' ? 'xlsx' : format, title: '银行研究成果', content_kind: 'evidence', evidence_ids: [source.evidence_id], limitations: '明确合成验收资料，非真实投资研究。' }
          if (format !== 'json') args.tables = [{ name: '对比数据', evidence_id: source.evidence_id, records_path: ['data', 'records'], columns: [
            { key: 'code', label: '证券代码', type: 'text' }, { key: 'name', label: '证券名称', type: 'text' },
            { key: 'price', label: '价格', type: 'number', unit: '元' }, { key: 'cost', label: '成本', type: 'number', unit: '元' },
            { key: 'rate', label: '变动比例', type: 'percent' }, { key: 'date', label: '资料日期', type: 'date' }, { key: 'note', label: '备注', type: 'text' },
          ] }]
        } else {
          assert.equal(previous().ok, true, JSON.stringify(previous()))
          text = `已生成 ${format.toUpperCase()} 合成研究成果及来源说明。请使用文件卡片的下载按钮保存；未知成本保留未知。这是受控数据与模型验收。`
        }
      }
      if (name) {
        const id = ToolCallId(`deliverable-${crypto.randomUUID()}`), argumentText = JSON.stringify(args)
        yield { type: 'block-start', index: 0, blockType: 'tool-call' }
        yield { type: 'tool-call-delta', index: 0, id, name, argumentsDelta: argumentText }
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id, name, arguments: argumentText } }
        yield { type: 'finish', reason: { kind: 'tool-calls' } }
      } else {
        yield { type: 'block-start', index: 0, blockType: 'text' }
        yield { type: 'text-delta', index: 0, text }
        yield { type: 'block-end', index: 0, block: { type: 'text', text } }
        yield { type: 'finish', reason: { kind: 'stop' } }
      }
    }
  }
  ctx.llm.registerAdapter(['huohuo-skills-fixture'], new Fixture())
}
