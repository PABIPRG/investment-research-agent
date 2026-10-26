import type { Context } from '@deepseek-ai/cordis'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { renderSkillContent } from '@deepseek-ai/dsh-skill'
import '@deepseek-ai/dsh-system-prompt'
import '@deepseek-ai/dsh-agent'
import type {} from '@deepseek-ai/dsh-app-boot'
import { readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

export const inject = ['tools', 'skills', 'systemPrompt', 'profileContext']
export const toolName = 'read_security_snapshot'

export async function apply(ctx: Context): Promise<void> {
  const skillBody = await readFile(new URL('../../../product/skills/bounded-quote/SKILL.md', import.meta.url), 'utf8')
  const skill = { name: 'huohuo-bounded-quote', description: '本次绑定对象的单次报价研究',
    content: skillBody.replace(/^---\n[\s\S]*?\n---\n/, ''), source: 'bundled', provider: 'huohuo',
    invocation: { modelInvocable: true, userInvocable: true } }
  ctx.skills.register(skill)
  const registered = await ctx.skills.get(skill.name)
  if (!registered || registered.provider !== 'huohuo') throw new Error('HUOHUO_SKILL_NOT_LOADED')
  ctx.systemPrompt.section({ name: 'huohuo:bounded-quote', order: 100, text: renderSkillContent(registered), interpolate: false })
  const binding = JSON.parse(process.env.HUOHUO_EXECUTION_BINDING ?? 'null')
  if (!binding?.execution_id || !binding?.scope) throw new Error('HUOHUO_BINDING_REQUIRED')
  ctx.systemPrompt.context({ name: 'huohuo:trusted-execution', order: 10, required: true, interpolate: false,
    text: '由产品服务赋予的执行边界：' + JSON.stringify(binding) })
  const definition: ToolDefinition = {
    name: toolName, description: '读取本次执行绑定的报价、公司资料或财务摘要，返回留存证据。只能执行固定 Scope，不能改变对象、期间或口径。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    output: { schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
    timeoutMs: 30_000,
    async execute(args, exec) {
      if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).length) throw new Error('HUOHUO_SCOPE_IS_FIXED')
      const base = new URL(process.env.HUOHUO_TOOL_API ?? '')
      if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || base.username || base.password) throw new Error('HUOHUO_INVALID_API')
      const attempt = process.env.HUOHUO_ATTEMPT_ID
      const token = process.env.HUOHUO_ATTEMPT_TOKEN
      if (!attempt || !token) throw new Error('HUOHUO_CAPABILITY_REQUIRED')
      const response = await fetch(new URL(`/attempts/${encodeURIComponent(attempt)}/research`, base), {
        method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: '{}',
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(25_000)]),
      })
      if (!response.ok) throw new Error(`HUOHUO_RESEARCH_HTTP_${response.status}`)
      return await response.json()
    },
  }
  ctx.tools.register(definition)
  ctx.tools.guard(exec => exec.name === toolName ? undefined : 'HUOHUO_TOOL_NOT_ALLOWED')
  ctx.on('agent/created', ({ agent }) => { agent.ctx.tools.restrict({ allow: [toolName] }); return undefined })
  const ackPath = process.env.HUOHUO_RUNTIME_ACK_PATH
  if (!ackPath) throw new Error('HUOHUO_ACK_REQUIRED')
  const dshManifest = JSON.parse(await readFile(new URL(import.meta.resolve('@deepseek-ai/dsh/package.json')), 'utf8'))
  await writeFile(ackPath, JSON.stringify({ version: '1.0.0', policy: 'bounded-research-v1', capability_manifest: { version: 1, operations: ['quote_snapshot', 'company_profile', 'financial_summary'] }, tools: [toolName],
    runtime: { pid: process.pid, argv: process.argv, executable: process.execPath, dsh_version: dshManifest.version,
      profile: { name: ctx.profileContext.name, directory: ctx.profileContext.dir, home: ctx.profileContext.home,
        started_bundles: ctx.profileContext.startedBundles } },
    execution_id: binding.execution_id, skill_sha256: createHash('sha256').update(skillBody).digest('hex') }), { flag: 'wx', mode: 0o600 })
}
