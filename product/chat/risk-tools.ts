import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { businessApi, businessTool, cancelled, confirmBusiness, type Ask } from './business-tools.js'

export const riskToolNames = ['assess_risk_preference', 'parse_risk_preferences', 'preview_risk_adjustment']
const tier = { type: 'string', enum: ['quick', 'full'] }
const candidates = {type:'array',maxItems:8,items:{type:'object',additionalProperties:false,properties:{qid:{type:'string',enum:['horizon','loss_tolerance','goal','income_stability','experience','drawdown_reaction','knowledge','product_pref']},option:{type:'integer',minimum:0,maximum:4}},required:['qid','option']}}
export function createRiskTools(address: string, token: string, ask?: Ask): ToolDefinition[] {
  const api = businessApi(address, token)
  return [businessTool('assess_risk_preference',
    '用户明确要求时发起三题或八题风险偏好问卷。可带用户原文及语义映射候选，缺答通过原生选项补齐，全部答案再次展示确认，程序按题库计分。画像用于风险预算与研究约束，不改持仓、已有委托或交易。取消不保存。',
    { tier, statement:{type:'string',minLength:1,maxLength:4000}, candidates }, ['tier'], async (a, exec) => {
      if (!ask) throw Error('原生问卷未接通，不能保存')
      const current = await api('/investment', exec)
      const bank = current.risk_questionnaire[a.tier] as { qid: string; title: string; options: string[] }[]
      if (a.candidates && !a.statement) throw Error('自然语言候选必须附用户原文，不能凭空代答')
      const draft = a.statement ? await api('/investment/risk-parse', exec, {tier:a.tier,text:a.statement,...(a.candidates?{candidates:a.candidates}:{})}) : {answers:[]}
      const proposed = new Map<string,number>(draft.answers.map((x:any)=>[x.qid,x.option]))
      const missing = bank.filter(q=>!proposed.has(q.qid))
      const result = missing.length ? await ask(missing.map(q => ({ id: 'risk-' + q.qid, header: '风险偏好', question: q.title,
        options: q.options.map(label => ({ label, description: '请选择最符合你当前情况的一项。' })) })),
        { ...exec, callId: (exec.callId + ':risk-questionnaire') as typeof exec.callId }) : {answers:[]}
      if (exec.signal.aborted || result?.pending || result?.cancelled || !Array.isArray(result?.answers) || result.answers.length !== missing.length) return cancelled
      const answers = bank.map(q => {
        if(proposed.has(q.qid))return {qid:q.qid,option:proposed.get(q.qid)!}
        const matches = result.answers.filter((x: any) => x.id === 'risk-' + q.qid)
        const answer = matches[0]
        if (matches.length !== 1 || answer.custom || !Array.isArray(answer.selected) || answer.selected.length !== 1) throw Error('问卷未完整选择原生选项，未保存')
        const option = q.options.indexOf(answer.selected[0])
        if (option < 0) throw Error('答案不在题库中，未保存')
        return { qid: q.qid, option }
      })
      const p = await api('/investment/preview', exec, { command: 'risk_profile', payload: { tier: a.tier, answers,...(a.statement?{statement:a.statement}:{}) } })
      const profile = p.after.risk_profile
      if (!await confirmBusiness(ask, exec, `确认保存风险偏好问卷？${a.statement?'\n原文：'+a.statement+'\n自然语言映射的答案也请逐项核对。':''}\n${profile.label}，${profile.score}/${profile.max_score} 分。\n${profile.answers.map((x: any) => bank.find(q => q.qid === x.qid)?.title + '：' + x.label).join('\n')}\n有效画像用于风险预算与研究约束；不改变持仓、已有委托、通知或交易。`)) return cancelled
      try {
        return { ok: true, data: await api('/investment/commit', exec, { preview_id: p.preview_id, request_key: p.preview_id }) }
      } catch (e) {
        return { ok: false, error: (e as any).code || 'business_operation_failed', preview_id: p.preview_id,
          guidance: '保存结果待核对。使用 commit_investment_change 读取同一预览回执；不要重新发起问卷。' }
      }
    }, true),
    businessTool('parse_risk_preferences','将用户原文映射为待核对题库答案。DSH 可提交从原文提取的选项索引，程序校验题目、重复和范围；不计分、不保存，缺答保持缺失。随后 assess_risk_preference 补答并确认。',
      {tier,text:{type:'string',minLength:1,maxLength:4000},candidates},['tier','text'],async(a,e)=>({ok:true,data:await api('/investment/risk-parse',e,a)})),
    businessTool('preview_risk_adjustment','预览滑块调整风险偏好。保留原问卷推断与分数；程序计算有效画像及预算。保存须 commit_investment_change 原生确认。',
      {risk_tolerance:{type:'number',minimum:0,maximum:1},horizon_years:{type:'integer',minimum:1,maximum:30}},['risk_tolerance','horizon_years'],async(a,e)=>({ok:true,data:await api('/investment/preview',e,{command:'risk_adjust',payload:a})}))]
}
