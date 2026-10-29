import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import {positionRiskQuestion} from '../position-risk-summary.js'
import {businessApi,businessTool,confirmBusiness,cancelled,requestKey,textField,versionField,type Ask} from './business-tools.js'
export const investmentToolNames = ['read_investment_facts','preview_investment_change','commit_investment_change','read_investment_collection','bind_mandate_investment_collection']
const number={type:'number',minimum:0,maximum:1e12}
const payload={type:'object',additionalProperties:false,properties:{ticker:{type:'string',pattern:'^[0-9]{6}$'},name:textField,quantity:number,cost_price:{anyOf:[number,{type:'null'}]},effective_at:textField,reason:{type:'string',maxLength:500},remove:{type:'boolean'},side:{type:'string',enum:['buy','sell']},price:{...number,exclusiveMinimum:0},fees:number,traded_at:textField,affects_holdings:{type:'boolean'},trade_request_id:textField,operation:{type:'string',enum:['amend','void']}}}
const labels:Record<string,string>={holding:'持仓录入/校正',watchlist:'自选变更',trade:'实际成交记录',revision:'成交更正/撤销'}
export function investmentQuestion(p:any):string{
  if(p.command==='position_risk')return positionRiskQuestion(p)
  if(p.command==='risk_adjust'){
    const r=p.after.risk_profile, policy=p.after.risk_policy
    return `确认调整风险偏好？${p.before.risk_profile.label} → ${r.label}。\n承受度 ${r.manual_adjust.risk_tolerance}，期限 ${r.manual_adjust.horizon_years} 年。原问卷答案与 ${r.score}/${r.max_score} 分保留。\n生效预算：单股权重上限 ${policy.risk_budget.single_stock_weight_max*100}%，集中度 HHI ${policy.risk_budget.hhi_max}。\n用于研究约束，不改持仓、已有委托、通知或交易。`
  }
  if(p.command==='risk_profile'){
    const r=p.after.risk_profile
    return `确认保存风险偏好？${r.label}，${r.score}/${r.max_score} 分。\n${r.answers.map((x:any)=>x.label).join('\n')}\n仅供研究背景，不改变持仓、委托、通知或交易。`
  }
  const a=p.payload, code=a.ticker||p.impact?.entry?.ticker
  const before=p.before.holdings.find((x:any)=>x.ticker===code), after=p.after.holdings.find((x:any)=>x.ticker===code)
  const unit=after?.quantity_unit||before?.quantity_unit||'股/份'
  const number=(v:any)=>v==null?'未知':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:6})
  const when=(v:any)=>v?new Date(v).toLocaleString('zh-CN'):'未提供'
  const values:Record<string,string>={buy:'买入',sell:'卖出',amend:'更正',void:'撤销'}
  const lines=[`确认${labels[p.command]||'投资记录'}？`, `证券：${a.name||after?.name||after?.display_name||p.impact?.entry?.name||before?.name||code||'原成交证券'}${code?'（'+code+'）':''}`]
  if(p.command==='watchlist')lines.push(`自选：${a.remove?'移除':'添加或更新'}；数量 ${p.before.watchlist.length} → ${p.after.watchlist.length}`)
  else {
    lines.push(`持仓数量：${before?number(before.quantity):p.before.holdings_status==='not_recorded'?'尚未录入':'0'} → ${after?number(after.quantity):'0'} ${unit}`,
      `单位成本：${number(before?.cost_price)} → ${number(after?.cost_price)} 元/${unit}`)
    if(a.side)lines.push(`已发生成交：${values[a.side]} ${number(a.quantity)} ${unit}，成交价格 ${number(a.price)} 元，费用 ${number(a.fees)} 元`)
    if(a.operation)lines.push(`修订方式：${values[a.operation]}`)
    if(typeof a.affects_holdings==='boolean')lines.push(`持仓处理：${a.affects_holdings?'同步更新持仓':'只补成交记录，不调整持仓'}`)
    if(a.traded_at||a.effective_at)lines.push(`发生/确认时间：${when(a.traded_at||a.effective_at)}`)
  }
  if(a.reason)lines.push(`原因：${a.reason}`)
  if(p.impact?.position_risk_impact?.length)lines.push(...p.impact.position_risk_impact,`依据事实版本 ${p.fact_version}。会按已确认的持仓风险约定更新对应委托；不向券商下单。`)
  else lines.push(`依据事实版本 ${p.fact_version}。保存不会向券商下单，不创建或结束委托；未知成本保留未知。`)
  return lines.join('\n')
}
export function createInvestmentTools(address:string,token:string,ask?:Ask):ToolDefinition[]{
 const api=businessApi(address,token)
 return [
  businessTool('read_investment_facts','读取本用户持仓、自选、成交、修订、版本及程序计算的 cost_analysis 成本集中度（非实时市值权重，缺成本时完整权重未知）。未录入不等于空仓。include_account=true 时查询同一本地账户的市值、日盈亏、数量、行情时间与缺口，成功空记录为0不代表券商空仓；读取失败不当0。新增/更正使用预览与确认工具。',{include_account:{type:'boolean'}},[],async(a,e)=>{
    try{return {ok:true,observed_at:new Date().toISOString(),data:a.include_account?{account:await api('/investment/account',e)}:await api('/investment',e)}}catch{return {ok:false,error:'investment_read_failed'}}
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
    if(!await confirmBusiness(ask,e,`为“${current.revision.goal}”关联${a.collection==='holdings'?'持仓':'自选'}？${a.mode==='fixed'?'固定当前快照':'每次使用最新集合'}，事实版本 ${snapshot.fact_version}。对象：${snapshot.members.map((x:any)=>`${x.name}（${x.entity_id.split(':').at(-1)}）`).join('、')||'已确认空集合'}。将产生新委托版本并撤销旧执行资格，不恢复暂停委托，不自动扩大研究对象。`))return cancelled
    return {ok:true,data:await api('/investment/bind-collection',e,{...a,request_key:requestKey(e,'bind-collection')})}
   },true)
 ]
}
