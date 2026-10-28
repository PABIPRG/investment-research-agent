import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import type { GenerateOptions, LlmAdapter, StreamChunk } from '@deepseek-ai/dsh-llm'
import { apply } from './progressive-model.js'
import { chatSkillNames } from '../product/chat/policy.js'
const user = (text: string) => ({
  role: 'user',
  source: { kind: 'user' },
  content: [{ type: 'text', text }],
})
test('预览对普通问题和未知回放明确提示，不触发断言或工具；不重用历史回放', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'huohuo-preview-input-'))
  const before = process.env.HUOHUO_SKILLS_PROOF
  process.env.HUOHUO_SKILLS_PROOF = join(dir, 'proof.jsonl')
  try {
    let adapter: LlmAdapter | undefined
    apply({
      llm: {
        registerAdapter: (_names: string[], value: LlmAdapter) => {
          adapter = value
        },
      },
    } as unknown as Context)
    const run = async (messages: unknown[]) => {
      const chunks: StreamChunk[] = []
      for await (const chunk of adapter!.stream({
        purpose: 'conversation',
        sessionId: 'preview-input-test',
        tools: [],
        messages,
      } as unknown as GenerateOptions))
        chunks.push(chunk)
      return chunks
    }
    for (const messages of [
      [user('我想先了解这次资料的缺口')],
      [user('回放 R99')],
      [user('回放 R05'), user('接着解释缺口')],
      [],
    ]) {
      const chunks = await run(messages)
      assert.equal(
        chunks.some((c) => c.type === 'tool-call-delta'),
        false,
      )
      assert.ok(chunks.some((c) => c.type === 'text-delta' && c.text.includes('没有执行研究')))
      assert.ok(chunks.some((c) => c.type === 'finish' && c.reason.kind === 'stop'))
    }
    const valid = await run([
      {
        role: 'user',
        source: { kind: 'catalog' },
        content: [
          {
            type: 'text',
            text: `<available_skills>${chatSkillNames.join(',')}</available_skills>`,
          },
        ],
      },
      user('回放 R01：你好'),
    ])
    assert.ok(valid.some((c) => c.type === 'text-delta' && c.text.includes('R01 受控回放')))
  } finally {
    if (before === undefined) delete process.env.HUOHUO_SKILLS_PROOF
    else process.env.HUOHUO_SKILLS_PROOF = before
    await rm(dir, { recursive: true, force: true })
  }
})
