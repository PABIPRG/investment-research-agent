import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { businessApi, businessTool, cancelled, confirmBusiness, type Ask } from './business-tools.js'

export const riskToolNames = ['assess_risk_preference']
export function createRiskTools(address: string, token: string, ask?: Ask): ToolDefinition[] {
  const api = businessApi(address, token)
  return [businessTool('assess_risk_preference',
    '用户明确要求时发起三题或八题风险偏好问卷。答案只取原生选项，程序计分并在保存前再次确认。结果仅供研究背景，不改变持仓、委托、通知或交易。取消不保存。读取已有结果用 read_investment_facts；提交未知用同一 preview_id 核对。',
    { tier: { type: 'string', enum: ['quick', 'full'] } }, ['tier'], async (a, exec) => {
      if (!ask) throw Error('原生问卷未接通，不能保存')
      const current = await api('/investment', exec)
      const bank = current.risk_questionnaire[a.tier] as { qid: string; title: string; options: string[] }[]
      const result = await ask(bank.map(q => ({ id: 'risk-' + q.qid, header: '风险偏好', question: q.title,
        options: q.options.map(label => ({ label, description: '请选择最符合你当前情况的一项。' })) })),
        { ...exec, callId: (exec.callId + ':risk-questionnaire') as typeof exec.callId })
      if (exec.signal.aborted || result?.pending || result?.cancelled || !Array.isArray(result?.answers) || result.answers.length !== bank.length) return cancelled
      const answers = bank.map(q => {
        const matches = result.answers.filter((x: any) => x.id === 'risk-' + q.qid)
        const answer = matches[0]
        if (matches.length !== 1 || answer.custom || !Array.isArray(answer.selected) || answer.selected.length !== 1) throw Error('问卷未完整选择原生选项，未保存')
        const option = q.options.indexOf(answer.selected[0])
        if (option < 0) throw Error('答案不在题库中，未保存')
        return { qid: q.qid, option }
      })
      const p = await api('/investment/preview', exec, { command: 'risk_profile', payload: { tier: a.tier, answers } })
      const profile = p.after.risk_profile
      if (!await confirmBusiness(ask, exec, `确认保存风险偏好问卷？\n${profile.label}，${profile.score}/${profile.max_score} 分。\n${profile.answers.map((x: any) => bank.find(q => q.qid === x.qid)?.title + '：' + x.label).join('\n')}\n仅供研究背景；不改变持仓、委托、通知或交易。`)) return cancelled
      try {
        return { ok: true, data: await api('/investment/commit', exec, { preview_id: p.preview_id, request_key: p.preview_id }) }
      } catch (e) {
        return { ok: false, error: (e as any).code || 'business_operation_failed', preview_id: p.preview_id,
          guidance: '保存结果待核对。使用 commit_investment_change 读取同一预览回执；不要重新发起问卷。' }
      }
    }, true)]
}
