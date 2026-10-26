import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import {businessApi,businessTool,confirmBusiness,cancelled,requestKey,textField,versionField,type Ask} from './business-tools.js'
export const investmentToolNames = ['read_investment_facts','preview_investment_change','commit_investment_change','read_investment_collection','bind_mandate_investment_collection']
const number={type:'number',minimum:0,maximum:1e12}
const payload={type:'object',additionalProperties:false,properties:{ticker:{type:'string',pattern:'^[0-9]{6}$'},name:textField,quantity:number,cost_price:{anyOf:[number,{type:'null'}]},effective_at:textField,reason:{type:'string',maxLength:500},remove:{type:'boolean'},side:{type:'string',enum:['buy','sell']},price:{...number,exclusiveMinimum:0},fees:number,traded_at:textField,affects_holdings:{type:'boolean'},trade_request_id:textField,operation:{type:'string',enum:['amend','void']}}}
const labels:Record<string,string>={holding:'持仓录入/校正',watchlist:'自选变更',trade:'实际成交记录',revision:'成交更正/撤销'}
export function investmentQuestion(p:any):string{
  const a=p.payload
  const codes=new Set([a.ticker,...(p.impact?.entry?.ticker?[p.impact.entry.ticker]:[])].filter(Boolean))
  const positions=(facts:any)=>(facts?.holdings||[]).filter((x:any)=>codes.size===0||codes.has(x.ticker)).map((x:any)=>({证券:x.name||x.ticker,代码:x.ticker,数量:x.quantity,单位:x.quantity_unit||'股/份',成本:x.cost_price??'未知'}))
  const fieldLabels:Record<string,string>={ticker:'证券代码',name:'证券名称',quantity:'数量',cost_price:'持仓成本',effective_at:'确认时间',reason:'原因',remove:'移除自选',side:'成交方向',price:'成交价格',fees:'费用',traded_at:'成交发生时间',affects_holdings:'同时更新持仓',trade_request_id:'原成交编号',operation:'修订方式'}
  const values:Record<string,string>={buy:'买入',sell:'卖出',amend:'更正',void:'撤销'}
  const details=Object.entries(a).filter(([k])=>fieldLabels[k]).map(([k,v])=>`${fieldLabels[k]}：${v===null?'未知':typeof v==='boolean'?(v?'是':'否'):values[String(v)]||String(v)}`).join('；')
  return `确认${labels[p.command]||'投资记录'}？事实版本 ${p.fact_version}。\n${details}\n持仓之前：${JSON.stringify(positions(p.before))}\n持仓之后：${JSON.stringify(positions(p.after))}\n${p.command==='watchlist'?`自选数量 ${p.before.watchlist.length} → ${p.after.watchlist.length}。`:''}保存不会向券商下单，也不会创建或结束委托。未知成本保留未知。`

}
export function createInvestmentTools(address:string,token:string,ask?:Ask):ToolDefinition[]{
 const api=businessApi(address,token)
 return [
  businessTool('read_investment_facts','读取本用户持仓、自选、成交、修订及版本。未录入不等于空仓。新增/更正使用预览与确认工具。',{},[],async(_a,e)=>{
    try{return {ok:true,observed_at:new Date().toISOString(),data:await api('/investment',e)}}catch{return {ok:false,error:'investment_read_failed'}}
  }),
  businessTool('preview_investment_change','预览持仓校正、自选、实际成交或修订。不会保存投资事实；确认具体代码、数量、已知成本及发生时间后使用。股票和场内基金均可记录；成本未知填 null。买卖须明确是否更新持仓，不能将计划当成交。',
   {command:{type:'string',enum:['holding','watchlist','trade','revision']},payload},['command','payload'],async(a,e)=>{
    const p={...a.payload}
    if(['trade','revision'].includes(a.command)){
      if(typeof p.affects_holdings!=='boolean')throw new Error('请确认只补记录还是同时更新持仓')
      p[a.command==='trade'?'request_id':'revision_id']=requestKey(e,a.command)
    }
    return {ok:true,data:await api('/investment/preview',e,{command:a.command,payload:p})}
   }),
  businessTool('commit_investment_change','读取已生成预览，程序展示真实影响并等待用户原生确认后保存。不能由模型填写确认结果。重复调用先核对已有回执；版本冲突重新预览。',{preview_id:{type:'string',pattern:'^[0-9a-f-]{36}$'}},['preview_id'],async(a,e)=>{
    const p=await api('/investment/previews/'+a.preview_id,e)
    if(p.receipt)return {ok:true,data:p.receipt,reconciled:true}
    if(!await confirmBusiness(ask,e,investmentQuestion(p)))return cancelled
    return {ok:true,data:await api('/investment/commit',e,{preview_id:p.preview_id,request_key:p.preview_id})}
   },true),
  businessTool('read_investment_collection','读取持仓或自选的当前/历史集合快照，用于预览委托上下文；不创建或修改委托。',{collection:{type:'string',enum:['holdings','watchlist']},version:{anyOf:[versionField,{type:'null'}]}},['collection'],async(a,e)=>({ok:true,data:await api('/investment/collection',e,{collection:a.collection,version:a.version??null})})),
  businessTool('bind_mandate_investment_collection','为已有委托关联固定/动态持仓或自选上下文。读取真实范围并由原生问答确认；产生新版本，不恢复暂停委托，不自动变为多证券研究。',{
   mandate_id:{type:'string',pattern:'^MND_[a-f0-9]{32}$'},collection:{type:'string',enum:['holdings','watchlist']},mode:{type:'string',enum:['fixed','dynamic']},expected_revision:{...versionField,minimum:1},expected_generation:versionField,expected_fact_version:versionField
  },['mandate_id','collection','mode','expected_revision','expected_generation','expected_fact_version'],async(a,e)=>{
    const current=await api('/mandates/'+a.mandate_id,e)
    const snapshot=await api('/investment/collection',e,{collection:a.collection,version:null})
    if(current.mandate.current_revision!==a.expected_revision||current.generation!==a.expected_generation||snapshot.fact_version!==a.expected_fact_version)throw new Error('委托或事实版本已变化，请重新读取')
    if(snapshot.status==='not_recorded'||current.mandate.status==='ended')throw new Error('尚未录入事实或委托已结束，不能关联')
    if(!await confirmBusiness(ask,e,`为“${current.revision.goal}”关联${a.collection==='holdings'?'持仓':'自选'}？${a.mode==='fixed'?'固定当前快照':'每次使用最新集合'}，事实版本 ${snapshot.fact_version}。对象：${snapshot.members.map((x:any)=>`${x.name} (${x.entity_id})`).join('、')||'已确认空集合'}。将产生新委托版本并撤销旧执行资格，不恢复暂停委托，不自动扩大研究对象。`))return cancelled
    return {ok:true,data:await api('/investment/bind-collection',e,{...a,request_key:requestKey(e,'bind-collection')})}
   },true)
 ]
}
