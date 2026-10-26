import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-agent'
import '@deepseek-ai/dsh-tools'
import { allowedChatToolNames } from './tools.js'
import { chatSkillNames } from './policy.js'
export const inject = ['tools']
export function apply(ctx: Context): void {
  ctx.tools.guard(exec => {
    if (!allowedChatToolNames.includes(exec.name)) return 'HUOHUO_CHAT_TOOL_NOT_ALLOWED'
    if (exec.name === 'skill') {
      const args = exec.arguments as { name?: unknown } | undefined
      if (!args || Object.keys(args).join(',') !== 'name' || !chatSkillNames.includes(args.name as string)) return 'HUOHUO_CHAT_SKILL_NOT_ALLOWED'
    }
    return undefined
  })
  ctx.on('agent/created', ({ agent }) => { agent.ctx.tools.restrict({ allow: allowedChatToolNames }); return undefined })
}
