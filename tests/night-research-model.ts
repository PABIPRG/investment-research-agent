/** 合成模型，仅用于隔离实例链路验收。 */
import type { Context } from '@deepseek-ai/cordis'
import { LlmAdapter, ToolCallId, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'
export const inject=['llm']
export function apply(ctx:Context) {
 class Fixture extends LlmAdapter {
  async listModels(route:string){return [{provider:route,id:'mandate-uat',name:'实体链路验收替身',inputModalities:['text' as const]}]}
  async resolveModel(route:string,id:string){return {provider:route,id,name:'实体链路验收替身',inputModalities:['text' as const],context:{contextWindow:128000},defaultMaxTokens:2048}}
  async *stream(options:GenerateOptions):AsyncIterable<StreamChunk>{
   const latest=options.messages.findLast(m=>m.role==='tool')
   const missing=options.messages.some(m=>m.role==='user'&&m.content.some(x=>x.type==='text'&&x.text.includes('缺口')))
   let name='',args:any={},text='合成财务研究验收'
   if(options.purpose!=='session-title') {
    let value:any;try{value=JSON.parse(latest?.content.filter(x=>x.type==='text').map(x=>x.text).join('')??'null')}catch{}
    if(!latest){name='resolve_research_scope';args={query:'600519财务摘要'}}
    else if(value?.data?.snapshot_id){name='confirm_research_entities';args={snapshot_id:value.data.snapshot_id,version:value.data.version}}
    else if(value?.confirmations?.length && options.messages.some(m=>m.role==='user'&&m.content.some(x=>x.type==='text'&&x.text.includes('确认委托')))){const c=value.confirmations[0];name='create_mandate';args={confirmation_id:c.confirmation_id,goal:missing?'合成缺口验收：半年报净利润':'合成基准验收：半年报营业总收入',scope:{entity_id:c.execution_entity_id,exchange:c.exchange,operation:'financial_summary',period:'20260630',metric:missing?'净利润':'营业总收入',basis:'source_abstract'},contact_note:'仅在产品查看；持续外部观察尚未启用'}}
    else text='已通过真实委托服务保存。请进入委托查询查看进展。'+(value?.ok?'已按明确委托创建合成财务摘要研究。外部持续观察与通知尚未启用。':value?.confirmations?.length?'已确认讨论对象，尚未创建委托。':'本次未确认对象，请补充名称后重试。')
   }
   if(name){const id=ToolCallId(name+'-entity-uat'),argumentsText=JSON.stringify(args);yield {type:'block-start',index:0,blockType:'tool-call'};yield {type:'tool-call-delta',index:0,id,name,argumentsDelta:argumentsText};yield {type:'block-end',index:0,block:{type:'tool-call',id,name,arguments:argumentsText}};yield {type:'finish',reason:{kind:'tool-calls'}};return}
   yield {type:'block-start',index:0,blockType:'text'};yield {type:'text-delta',index:0,text};yield {type:'block-end',index:0,block:{type:'text',text}};yield {type:'finish',reason:{kind:'stop'}}
  }
 }
 ctx.llm.registerAdapter(['huohuo-night-uat'],new Fixture())
}
