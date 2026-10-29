import type {ToolDefinition} from '@deepseek-ai/dsh-tools'
import {businessApi,businessTool} from './business-tools.js'
export const researchReviewToolNames=['review_research_decision','read_research_reviews']
const score={type:['number','null'],minimum:0,maximum:1}
const evidence={type:'array',maxItems:10,uniqueItems:true,items:{type:'string',minLength:1,maxLength:200}}
const signal={type:'object',additionalProperties:false,properties:{
  action:{type:'string',enum:['买入','持有','卖出','观望','无法判断']},risk_score:score,confidence:score,
  target_price:{type:['number','null'],exclusiveMinimum:0,maximum:1e12},reasoning:{type:'string',minLength:1,maxLength:4000}
},required:['action','risk_score','confidence','target_price','reasoning']}
export function createResearchReviewTools(address:string,token:string):ToolDefinition[]{
  const api=businessApi(address,token)
  return [businessTool('review_research_decision','保存 DSH 的结构化个股研究，并按当前用户已确认风险画像执行旧版确定性护栏。先确认沪深A股，引用本会话同主体成功证据；程序绑定画像版本和时间，保留原建议及校准结果。perspectives 用九种研究视角；缺资料写明限制并留空引用，风险分未知用 null。未录画像/风险分/证据不产生默认持有结论。不会创建委托、提醒或交易。',{
    confirmation_id:{type:'string',minLength:1,maxLength:200},signal,
    perspectives:{type:'array',maxItems:9,items:{type:'object',additionalProperties:false,properties:{
      role:{type:'string',enum:['fundamentals','technical','news','sentiment','bull','bear','risk_aggressive','risk_neutral','risk_conservative']},
      summary:{type:'string',minLength:1,maxLength:2000},evidence_ids:evidence
    },required:['role','summary','evidence_ids']}}
  },['confirmation_id','signal','perspectives'],async(a,e)=>({ok:true,data:await api('/research-reviews/run',e,{session_id:e.agent!.session.id,call_id:e.callId,arguments:a})})),
  businessTool('read_research_reviews','读取当前主体最近的结构化研究、当时的风险画像、原始与校准建议及证据引用。旧研究不是当前行情或当前画像，最多50条；不自动重评或创建跟踪。',
    {limit:{type:'integer',minimum:1,maximum:50}},[],async(a,e)=>({ok:true,data:await api('/research-reviews/history',e,a)}))]
}
