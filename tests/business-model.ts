/** 真实 DSH 工具与原生用户确认的合成场景；绝不用于真实投研。 */
import assert from 'node:assert/strict'
import {appendFile} from 'node:fs/promises'
import type {Context} from '@deepseek-ai/cordis'
import {LlmAdapter,ToolCallId,type GenerateOptions,type StreamChunk} from '@deepseek-ai/dsh-llm'
export const inject=['llm']
export function apply(ctx:Context){
 assert.ok(process.env.HUOHUO_SKILLS_PROOF)
 class Fixture extends LlmAdapter{
  async listModels(provider:string){return [{provider,id:'controlled',name:'业务写入受控回放',inputModalities:['text' as const]}]}
  async resolveModel(provider:string,id:string){return {provider,id,name:'业务写入受控回放',inputModalities:['text' as const],context:{contextWindow:128000},defaultMaxTokens:2048}}
  async *stream(options:GenerateOptions):AsyncIterable<StreamChunk>{
   let name='',args:any={},text='业务写入受控回放'
   if(options.purpose!=='session-title'){
    const start=options.messages.findLastIndex(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&/回放 B\d+/.test(b.text)))
    assert.ok(start>=0,'请输入回放 B01/B02/B03/B04/B05/B06')
    const input=options.messages[start].content.filter(b=>b.type==='text').map(b=>b.text).join(''),id=/回放 (B\d+)/.exec(input)![1]
    const seq:Record<string,string[]>={
     B01:['huohuo-investment-facts','read_investment_facts','preview_investment_change','commit_investment_change','open_product_view'],
     B02:['huohuo-investment-facts','read_investment_facts','preview_investment_change','commit_investment_change'],
     B03:['huohuo-notifications','read_notification_settings','update_notification_preferences','open_product_view'],
     B04:['huohuo-mandates','list_mandates','read_investment_collection','bind_mandate_investment_collection'],
     B05:['huohuo-mandates','list_mandates','manage_mandate'],
     B07:['huohuo-mandates','resolve_research_scope','confirm_research_entities','create_mandate'],
     B09:['huohuo-mandates','resolve_research_scope','confirm_research_entities','create_mandate'],
     B08:['open_product_view'],
     B06:['huohuo-notifications','read_notification_settings','list_notification_deliveries','open_product_view'],
    }
    const sequence=seq[id];assert.ok(sequence)
    const results=options.messages.slice(start+1).filter(m=>m.role==='tool'),step=results.length
    const result=(tool:string):any=>{try{return JSON.parse(results[sequence.indexOf(tool)]?.content.filter(b=>b.type==='text').map(b=>b.text).join('')||'null')}catch{return null}}
    const action=sequence[step]
    if(action){
     name=action
     if(action.startsWith('huohuo-')){name='skill';args={name:action}}
     if(action==='preview_investment_change')args={command:'holding',payload:{ticker:id==='B02'?'159740':'513130',name:id==='B02'?'合成恒生科技ETF乙':'合成恒生科技ETF甲',quantity:id==='B02'?200:1000,cost_price:null,effective_at:'2026-01-01T00:00:00+08:00',reason:'用户提供的期初快照，合成验收'}}
     if(action==='commit_investment_change')args={preview_id:result('preview_investment_change').data.preview_id}
     if(action==='open_product_view')args={view:id==='B08'?'settings':id==='B01'?'investment':'notifications'}
     if(action==='resolve_research_scope')args={query:id==='B09'?'600519 行情条件跟进':'600519 财务摘要',mention_texts:['600519']}
     if(action==='confirm_research_entities'){const r=result('resolve_research_scope').data;args={snapshot_id:r.snapshot_id,version:r.version}}
     if(action==='create_mandate'){const c=result('confirm_research_entities').confirmations[0];args={confirmation_id:c.confirmation_id,goal:'合成验收集合与提醒',scope:{entity_id:c.execution_entity_id,exchange:c.exchange,operation:'financial_summary',period:'20260630',metric:'营业总收入',basis:'source_abstract'},contact_note:'仅应用内，不发送外部通知'}}
     if(action==='create_mandate'&&id==='B09'){const c=result('confirm_research_entities').confirmations[0];args={confirmation_id:c.confirmation_id,goal:'合成验收：报价从90变为110时按条件联系',scope:{entity_id:c.execution_entity_id,exchange:c.exchange,operation:'market_quote'},contact_note:'仅应用内，不发送外部通知',contact_rule:{mode:'condition',condition:{type:'numeric',metric:'price',operator:'>=',threshold:100},notify_on:'transition',cooldown_minutes:0}}}
     if(action==='update_notification_preferences'){const c=result('read_notification_settings').data;args={expected_revision:c.revision,enabled:false,channels:['app'],timezone:'Asia/Shanghai',quiet_hours:{start:'22:00',end:'08:00'}}}
     if(action==='read_investment_collection')args={collection:'holdings'}
     if(action==='bind_mandate_investment_collection'){const m=result('list_mandates').data.items[0],c=result('read_investment_collection').data;args={mandate_id:m.mandate.mandate_id,collection:'holdings',mode:'fixed',expected_revision:m.mandate.current_revision,expected_generation:m.generation,expected_fact_version:c.fact_version}}
     if(action==='manage_mandate'){const m=result('list_mandates').data.items[0];args={mandate_id:m.mandate.mandate_id,action:'revise',expected_revision:m.mandate.current_revision,expected_generation:m.generation,definition:{goal:m.revision.goal,scope:m.revision.scope,contact_note:'每日北京时间09点应用内提醒；合成验收',reminder_time:'09:00',contact_channels:['app']}}}
    }else{
     const commit=result('commit_investment_change')||result('update_notification_preferences')||result('bind_mandate_investment_collection')||result('manage_mandate')||result('create_mandate')
     text=`${id} 合成回放完成。`+(commit?.saved===false?'你取消了本次操作，未保存。':commit?.ok?'业务服务已返回保存回执。':commit?'操作未完成，请核对工具错误。':id==='B08'?'入口已准备，请点击打开。':'已读取脱敏配置及真实投递列表。')
     const nav=result('open_product_view');if(nav?.navigation_required)text+=nav.guidance;if(nav?.url)text+=` [${nav.label}](${nav.url})`
    }
    await appendFile(process.env.HUOHUO_SKILLS_PROOF!,JSON.stringify({case:id,step,call:name||null,status:name?'stepping':'completed',session:options.sessionId})+'\n')
   }
   if(name){const id=ToolCallId('business-'+crypto.randomUUID()),argumentsText=JSON.stringify(args);yield {type:'block-start',index:0,blockType:'tool-call'};yield {type:'tool-call-delta',index:0,id,name,argumentsDelta:argumentsText};yield {type:'block-end',index:0,block:{type:'tool-call',id,name,arguments:argumentsText}};yield {type:'finish',reason:{kind:'tool-calls'}};return}
   yield {type:'block-start',index:0,blockType:'text'};yield {type:'text-delta',index:0,text};yield {type:'block-end',index:0,block:{type:'text',text}};yield {type:'finish',reason:{kind:'stop'}}
  }
 }
 ctx.llm.registerAdapter(['huohuo-skills-fixture'],new Fixture())
}
