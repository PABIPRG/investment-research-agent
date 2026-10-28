import { createHash } from 'node:crypto'
import type { ToolDefinition, ToolRunContext } from '@deepseek-ai/dsh-tools'
export const strategyToolNames = ['read_strategy_records', 'manage_strategy']
export type StrategyQuestion = (questions: unknown[], exec: ToolRunContext) => Promise<any>
const text = { type: 'string', minLength: 1, maxLength: 1000 }
const fields = {
  name: text, kind: { type: 'string', enum: ['ma_cross','momentum','rsi_reversal','breakout','bollinger','volume_breakout'] },
  params: { type: 'object', properties: Object.fromEntries(['fast','slow','n','oversold','overbought','k','vol_mult'].map(x=>[x,{type:'number'}])), additionalProperties:false },
  securities: { type:'array',minItems:1,maxItems:3,items:{type:'object',properties:{code:{type:'string',pattern:'^[0-9]{6}$'},name:text},required:['code','name'],additionalProperties:false} },
  source_evidence_ids:{type:'array',maxItems:5,items:text},rationale:text,direction:{type:'string',enum:['利好','利空','其他']},strategy_id:text,
  scope:{type:'string',enum:['pool']},state_version:text,revision:{type:'integer',minimum:0},start_date:text,end_date:text,preview_token:text,
  suggestion_id:text,enabled:{type:'boolean'},daily_time:{type:'string',pattern:'^(1[6-9]|2[0-3]):[0-5][0-9]$'},
  strategy_ids:{type:'array',maxItems:100,items:text},actions:{type:'array',minItems:1,maxItems:3,items:{type:'string',enum:['backtest','shadow','evolve']}},
  retest_days:{type:'integer',minimum:1,maximum:365},lookback_days:{type:'integer',minimum:40,maximum:1095},event_candidates:{type:'boolean'},archive_recall:{type:'boolean'},
}
export function strategyConfirmed(answer:any):boolean {
  return Array.isArray(answer?.answers) && answer.answers.length===1 && answer.answers[0].id==='strategy-confirm'
    && !answer.answers[0].custom && Array.isArray(answer.answers[0].selected)
    && answer.answers[0].selected.length===1 && answer.answers[0].selected[0]==='确认执行'
}
export function createStrategyTools(address:string,token:string,ask?:StrategyQuestion):ToolDefinition[] {
  const base=new URL(address)
  if(base.protocol!=='http:'||base.hostname!=='127.0.0.1'||!base.port||base.pathname!=='/'||base.username||base.password||base.search||base.hash||!token)throw Error('策略 API 配置无效')
  return strategyToolNames.map(name=>({
    name,description:name==='read_strategy_records'
      ? '查询当前实例策略的名称、规则、真实 revision、验证状态、回测/影子记录和进化预案。同时查询 automation 后台约定、suggestions 待确认建议、background_jobs 与 planner_jobs。空记录不代表策略无效。'
      : '按明确需求保存候选、回测、更新影子验证、生成/应用进化预案或停止策略。程序先预览并等待原生用户确认；模型不能提供确认回答。create需名称、规则参数、证券名称/代码、假设、方向；全池 evolve/apply 使用 scope=pool 和最新 state_version；其他操作需最新strategy_id/revision，backtest另需起止日期，apply另需当前preview_token。schedule 使用查询返回的 automation revision 及完整计划字段，显式确认启用/停用；不能自动扩大策略范围。accept_suggestion 使用 suggestion_id，确认后保存待验证候选。仅做多研究模拟，不执行交易。',
    parameters:name==='read_strategy_records'
      ? {type:'object',properties:{strategy_id:text,request_key:text},required:[],additionalProperties:false}
      : {type:'object',properties:{action:{type:'string',enum:['create','backtest','shadow','evolve','apply','retire','schedule','accept_suggestion']},payload:{type:'object',properties:fields,additionalProperties:false}},required:['action','payload'],additionalProperties:false},
    output:{schema:{type:'object',additionalProperties:true},render:(_a:any,v:any)=>[{type:'text',text:JSON.stringify(v)}]},
    timeoutMs:2147483000,
    async execute(input:any,exec:ToolRunContext){
      const session=exec.agent?.session.id
      if(!session||!exec.callId||!input||typeof input!=='object'||Array.isArray(input))throw Error('缺少可信会话或参数无效')
      const read=name==='read_strategy_records'
      if(Object.keys(input).some(k=>!(read?['strategy_id','request_key']:['action','payload']).includes(k)))throw Error('参数包含未允许字段')
      const key='strategy:'+createHash('sha256').update(JSON.stringify([session,exec.callId])).digest('hex')
      async function request(path:string,body:any,timeout=15000){
        const r=await fetch(new URL('/strategies/'+path,base),{method:'POST',redirect:'error',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
          body:JSON.stringify(body),signal:AbortSignal.any([exec.signal,AbortSignal.timeout(timeout)])})
        const value=await r.json() as any
        if(!r.ok)throw Error(value.detail||'策略请求未完成，请查询最新记录')
        return value
      }
      try {
        if(read)return await request('query',input)
        if(!ask)throw Error('原生确认未装配，未执行策略变更')
        const preview=await request('prepare',{session_id:session,request_key:key,...input})
        const answer=await ask([{id:'strategy-confirm',header:'确认策略操作',question:preview.summary,
          options:[{label:'确认执行',description:'按此预览执行；不进行真实交易。'},{label:'暂不执行',description:'保留讨论，不修改策略或发起计算。'}]}],exec)
        if(!strategyConfirmed(answer)||exec.signal.aborted)return {status:'cancelled',guidance:'用户未确认，未提交策略操作。'}
        return await request('commit',{session_id:session,preview_id:preview.preview_id,request_key:key},110000)
      }catch(e){return {status:'unconfirmed',error:e instanceof Error?e.message:'策略连接中断',request_key:key,
        guidance:'提交结果未知时先用 read_strategy_records 查询运行回执，不得自动更换请求标识重放。'} }
    },
  }))
}
