import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
export const investmentToolNames = ['read_investment_facts']
export function createInvestmentTools(address:string,token:string):ToolDefinition[]{
 return [{name:investmentToolNames[0],description:'只读当前用户统一持仓、自选、操作记录与事实版本。读取失败不代表空仓，建议不等于成交；新增或更正请引导至持仓与自选页面预览确认。',parameters:{type:'object',properties:{},required:[],additionalProperties:false},output:{schema:{type:'object',additionalProperties:true},render:(_a,v)=>[{type:'text',text:JSON.stringify(v)}]},timeoutMs:15000,async execute(input,exec){
  if(!input||typeof input!=='object'||Object.keys(input).length||!exec.agent?.session.id)throw new Error('缺少可信会话或参数无效')
  try{const r=await fetch(new URL('/investment',address),{headers:{Authorization:`Bearer ${token}`},redirect:'error',signal:AbortSignal.any([exec.signal,AbortSignal.timeout(10000)])});return r.ok?{ok:true,data:await r.json()}:{ok:false,error:'investment_read_failed'}}catch{return {ok:false,error:'investment_read_failed'}}
 }}]
}
