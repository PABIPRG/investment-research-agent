import type { Context } from '@deepseek-ai/cordis'
import type { ToolDefinition, ToolRunContext } from '@deepseek-ai/dsh-tools'
import { ToolCallId } from '@deepseek-ai/dsh-llm'

export const entityToolName = 'confirm_research_entities'
export function confirmationQuestions(snapshot: any, reconfirm = false) {
  return snapshot.mentions.filter((m: any) => m.candidates.length && (reconfirm || !m.confirmation)).map((m: any) => ({
    id: m.mention_id, header: '确认对象', question: `“${m.raw_text}”指的是哪一个对象？这里只确认讨论对象，不创建持续委托。`,
    options: [...m.candidates.map((c: any) => ({ label: candidateLabel(c), description: c.entity_type_code === 'ENTITY_01_01' ? '证券身份；可用于受控沪深 A 股研究。' : c.entity_type_code === 'ENTITY_02_01' ? '上市公司身份；与股票分开记录。' : '可识别对象；当前尚不支持执行研究。' })), { label: '重新说明对象', description: '不确认本项，继续补充名称或代码。' }],
  }))
}
function candidateLabel(c: any): string {
  const kind = c.entity_type_code === 'ENTITY_01_01' ? '股票' : c.entity_type_code === 'ENTITY_02_01' ? '上市公司' : '研究对象'
  return c.entity_type_code === 'ENTITY_01_01' || c.entity_type_code === 'ENTITY_02_01' ? `${c.canonical_name} · ${kind} · ${c.entity_id.split(':').at(-1)}` : `${c.canonical_name} · ${kind}`
}
export function choicesFromAnswer(snapshot: any, answer: any): Record<string,string> {
  const choices: Record<string,string> = {}
  if (!Array.isArray(answer?.answers)) return choices
  for (const m of snapshot.mentions) {
    const entries = answer.answers.filter((a: any) => a.id === m.mention_id)
    if (entries.length !== 1) continue
    const a = entries[0]
    if (a.custom || !Array.isArray(a.selected) || a.selected.length !== 1) continue
    const matches = m.candidates.filter((c: any) => candidateLabel(c) === a.selected[0])
    if (matches.length === 1) choices[m.mention_id] = matches[0].entity_id
  }
  return choices
}
export function createEntityConfirmationTool(address: string, token: string, ask: (questions: unknown[], exec: ToolRunContext) => Promise<any>): ToolDefinition {
  return {
    name: entityToolName, description: '对 resolve_research_scope 返回的快照发起原生选项确认。程序生成候选问题并保存真实用户回答，不能由模型填写确认结果。多对象逐项选择。自由输入或跳过不确认；本工具不创建委托。',
    parameters: { type: 'object', properties: { snapshot_id: { type: 'string' }, version: { type: 'string' }, reconfirm: {type:'boolean',description:'用户要求改选时设为 true，重新展示所有候选。'} }, required: ['snapshot_id','version'], additionalProperties: false },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a,v) => [{ type:'text',text:JSON.stringify(v) }] },
    // 用户确认不可由超时替代。
    timeoutMs: 2147483000,
    async execute(input, exec) {
      const args = input as any; const session = exec.agent?.session.id
      if (!session || !exec.callId || !args || !['snapshot_id,version','reconfirm,snapshot_id,version'].includes(Object.keys(args).sort().join(','))) throw new Error('缺少可信会话或候选快照')
      const body = { session_id: session, snapshot_id: args.snapshot_id, version: args.version }
      const request = async (path: string, payload: unknown) => {
        const response = await fetch(new URL(path,address), { method:'POST', headers:{ Authorization:`Bearer ${token}`,'Content-Type':'application/json' }, body:JSON.stringify(payload), redirect:'error',signal:AbortSignal.any([exec.signal,AbortSignal.timeout(15000)]) })
        const data = await response.json() as any
        if (!response.ok) throw new Error(data.detail || '实体确认暂不可用，请重新查询')
        return data
      }
      const snapshot = await request('/entities/snapshot',body)
      const questions = confirmationQuestions(snapshot,args.reconfirm === true)
      const existing = snapshot.mentions.filter((m:any)=>m.confirmation && args.reconfirm !== true).map((m:any)=>m.confirmation)
      if (!questions.length) return existing.length ? { confirmations:existing,mandate_created:false,guidance:'复用本对话仍有效的对象确认；未创建委托。' } : { confirmed:false,guidance:'没有可确认候选，请补充完整名称或代码。' }
      const answer = await ask(questions,exec)
      const choices = choicesFromAnswer(snapshot,answer)
      if (!Object.keys(choices).length) return { confirmed:false,guidance:'未确认任何对象；请根据补充内容重新解析。' }
      const saved=await request('/entities/confirm',{ ...body,choices,source_call:`${exec.callId}:entities` });return {...saved,confirmations:[...existing,...saved.confirmations]}
    },
  }
}
export function nativeEntityQuestion(ctx: Context) {
  return async (questions: unknown[], exec: ToolRunContext) => {
    const result = await ctx.tools.execute({ name:'ask_user_question',callId:ToolCallId(`${exec.callId}:entities`),rootCallId:exec.rootCallId,parent:exec.token,agent:exec.agent,signal:exec.signal,arguments:{ timeout:-1,questions } })
    if (result.isError) throw new Error('对象确认未完成，请重试')
    return result.value
  }
}
