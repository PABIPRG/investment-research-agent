/** 受控生成结果适配 DSH 的公开交付协议；不开放任意 present 路径。 */
import type { Context } from '@deepseek-ai/cordis'
import type { ToolRunContext } from '@deepseek-ai/dsh-tools'
import '@deepseek-ai/dsh-session-projection'
import '@deepseek-ai/dsh-agent-loop'
import '@deepseek-ai/dsh-tool-present/types'
import type { ResearchFile } from './deliverable-tools.js'

export function deliveryRecorder(ctx: Context) {
  const pending = new WeakMap<object, ResearchFile>()
  ctx.on('tools/result', (exec, result) => {
    const file = pending.get(exec)
    pending.delete(exec)
    if (!file || result.isError || !exec.agent) return
    const turn = ctx.sessionProjections.stateOf(exec.agent.session, 'turnBoundary')
    if (!turn || turn.openTurnStartSeq === null) return
    exec.agent.session.append('deliverables/presented', {
      turn: turn.lastTurn, callId: exec.callId,
      files: [
        { path: file.file_path, description: `${file.content_kind === 'evidence' ? '原始资料' : '模型整理'} · ${file.bytes} 字节 · 使用下载保存副本` },
        { path: file.metadata_path, description: '来源原始记录、生成时间、字段单位与限制' },
      ],
    })
    return undefined
  })
  return (exec: ToolRunContext, file: ResearchFile) => { pending.set(exec, file) }
}
