import {personalizationQuestion} from '../personalization-summary.js'
import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import {createHash} from 'node:crypto'
import {businessApi,businessTool,confirmBusiness,cancelled,requestKey,type Ask} from './business-tools.js'
export const personalizationToolNames=['read_personalized_research','preview_personalization_change','commit_personalization_change','refresh_personalized_sources','record_personalized_interaction']
export function createPersonalizationTools(address:string,token:string,ask?:Ask):ToolDefinition[]{
  const api=businessApi(address,token)
  return [
    businessTool('record_personalized_interaction','记录当前聊天中用户实际打开或要求带入分析的一张现有资讯/策略/风险卡片。先读取卡片真实ID；不能把模型自动读取列表当作用户兴趣。仅已明确启用本机学习时记入，暂停时忽略；身份、会话、时间、证券和兴趣元数据由程序绑定，重复调用回查原回执，不修改风险画像或创建委托。',
      {card_id:{type:'string',minLength:1,maxLength:120},action:{type:'string',enum:['open','analyze']}},['card_id','action'],async(a,e)=>({ok:true,data:await api('/personalization/record',e,{...a,
        request_key:requestKey(e,'record_personalized_interaction'),session_id:'chat:'+createHash('sha256').update(e.agent!.session.id).digest('hex'),surface:'assistant'})})),
    businessTool('read_personalized_research','读取本实例个性化卡片、策略匹配、兴趣画像、反馈、学习开关与偏好复盘。读取现有资料，不自动抓取、跟踪或启用学习；空卡片不等于市场无事件。',
      {offset:{type:'integer',minimum:0,maximum:100},days:{type:'integer',enum:[7,30,90]}},[],async(a,e)=>({ok:true,data:await api('/personalization/read',e,a)})),
    businessTool('preview_personalization_change','预览启用/暂停本机学习、清除本机学习记录或对当前卡片反馈。不会保存。使用 commit_personalization_change 展示影响并等待用户确认。',
      {action:{type:'string',enum:['learning','clear','feedback']},enabled:{type:'boolean'},card_id:{type:'string',maxLength:120},sentiment:{type:'string',enum:['useful','useless','neutral']}},['action'],async(a,e)=>({ok:true,data:await api('/personalization/preview',e,a)})),
    businessTool('commit_personalization_change','读取原预览并在原生确认后保存本机偏好变更。已存在回执直接回查，连接中断保留同一 preview_id；不重新提交另一个操作。',
      {preview_id:{type:'string',pattern:'^[0-9a-f-]{36}$'}},['preview_id'],async(a,e)=>{
        const p=await api('/personalization/previews/'+a.preview_id,e)
        if(p.receipt)return {ok:true,data:p.receipt,reconciled:true}
        if(!await confirmBusiness(ask,e,personalizationQuestion(p)))return cancelled
        try{return {ok:true,data:await api('/personalization/commit',e,{preview_id:a.preview_id,request_key:a.preview_id})}}
        catch{return {ok:false,error:'submission_unknown',preview_id:a.preview_id,guidance:'先用同一预览核对回执，不创建第二个操作。'}}
      },true),
    businessTool('refresh_personalized_sources','按当前已记录沪深 A 股持仓与自选读取一次最新相关资讯，最多20只，复用现有资料来源。不会创建连续跟踪、委托或通知；来源失败不等于无事件。',{},[],async(_a,e)=>({ok:true,data:await api('/personalization/refresh',e,{})}))
  ]
}
