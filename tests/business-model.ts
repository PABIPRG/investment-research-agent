/** 真实 DSH 工具与原生用户确认的合成场景；绝不用于真实投研。 */
import assert from 'node:assert/strict'
import {appendFile} from 'node:fs/promises'
import type {Context} from '@deepseek-ai/cordis'
import {LlmAdapter,ToolCallId,type GenerateOptions,type StreamChunk} from '@deepseek-ai/dsh-llm'
export const inject=['llm']
async function* companionStages(options:GenerateOptions):AsyncIterable<StreamChunk>{
 const hasResult=options.messages.some(m=>m.content.some(b=>b.type==='text'&&b.text.includes('回放 B13'))||m.role==='tool'&&m.content.some(b=>b.type==='text'&&b.text.includes('明确合成')))
 if(!hasResult){
  yield {type:'block-start',index:0,blockType:'reasoning'}
  for(let i=0;i<20;i++){options.signal?.throwIfAborted();yield {type:'reasoning-delta',index:0,text:'正在对照合成资料。'};await new Promise(r=>setTimeout(r,500))}
  yield {type:'block-end',index:0,block:{type:'reasoning',text:'正在对照合成资料。'}}
  const id=ToolCallId('companion-'+crypto.randomUUID()),name='query_market',args=JSON.stringify({operation:'news',limit:3})
  yield {type:'block-start',index:1,blockType:'tool-call'}
  yield {type:'tool-call-delta',index:1,id,name,argumentsDelta:args}
  yield {type:'block-end',index:1,block:{type:'tool-call',id,name,arguments:args}}
  yield {type:'finish',reason:{kind:'tool-calls'}}
 }else{
  yield {type:'block-start',index:0,blockType:'text'}
  for(let i=0;i<20;i++){options.signal?.throwIfAborted();yield {type:'text-delta',index:0,text:'合成资料已返回，正在整理说明。'};await new Promise(r=>setTimeout(r,500))}
  yield {type:'block-end',index:0,block:{type:'text',text:'B12 合成阶段回放完成。'}}
  yield {type:'finish',reason:{kind:'stop'}}
 }
}
export function apply(ctx:Context){
 assert.ok(process.env.HUOHUO_SKILLS_PROOF)
 class Fixture extends LlmAdapter{
  async listModels(provider:string){return [{provider,id:'controlled',name:'业务写入受控回放',inputModalities:['text' as const]}]}
  async resolveModel(provider:string,id:string){return {provider,id,name:'业务写入受控回放',inputModalities:['text' as const],context:{contextWindow:128000},defaultMaxTokens:2048}}
  async *stream(options:GenerateOptions):AsyncIterable<StreamChunk>{
   if(options.purpose!=='session-title'&&options.messages.some(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&/回放 B1[23]/.test(b.text)))){
    yield* companionStages(options);return
   }
   let name='',args:any={},text='业务写入受控回放'
   if(options.purpose!=='session-title'){
    const start=options.messages.findLastIndex(m=>m.role==='user'&&m.content.some(b=>b.type==='text'&&/回放 B\d+/.test(b.text)))
    assert.ok(start>=0,'请输入回放 B01/B02/B03/B04/B05/B06')
    const input=options.messages[start].content.filter(b=>b.type==='text').map(b=>b.text).join(''),id=/回放 (B\d+)/.exec(input)![1]
    const seq:Record<string,string[]>={
     B16:['ask_user_question'],
     B15:['huohuo-investment-facts','read_personalized_research','record_personalized_interaction','read_personalized_research'],
     B14:['huohuo-research-chat','resolve_research_scope','confirm_research_entities','query_market','review_research_decision','read_research_reviews'],
     B10:['huohuo-investment-facts','assess_risk_preference','read_investment_facts'],
     B11:['huohuo-investment-facts','assess_risk_preference','read_investment_facts'],
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
     if(action==='ask_user_question')args={timeout:-1,questions:[
      {id:'context',header:'问答样式验收',question:'收到提醒后，你希望怎样查看大盘和行业的情况？（明确合成，仅验证样式）',options:[
       {label:'收到提醒后问我，我现场查（推荐）',description:'你收到提醒后说一声，我再查询大盘、行业和个股资料，保留原始来源与时间，方便逐项对照。'},
       {label:'另建一份收盘后的研究简报',description:'这是较长的说明：简报按独立研究约定运行，资料覆盖和来源以实际返回为准。本次回放不会创建任何委托，也不会发送外部通知。'},
       {label:'保持现有安排',description:'只保留当前提醒，不新增任何研究安排。'}]},
      {id:'sources',header:'多选与滚动验收',multi_select:true,question:'你希望对照哪些研究资料？（可多选，仅合成验收）',options:[
       {label:'大盘与市场概况',description:'核对市场涨跌、成交与时间范围，资料不足时保留未知，不补写未经证实的结论。'},
       {label:'行业与板块背景',description:'查看行业范围、成分口径与板块差异，长说明应完整换行，并能在窄屏内滚动阅读。'},
       {label:'公司公开披露',description:'依据公开公告和定期报告核对经营变化，保留来源与报告期。'},
       {label:'历史研究记录',description:'对照此前研究中的支持证据、反证与待补材料，本次不修改任何真实记录。'}]}
     ]}
     if(action==='assess_risk_preference')args={tier:id==='B11'?'full':'quick'}
     if(action==='preview_investment_change')args={command:'holding',payload:{ticker:id==='B02'?'159740':'513130',name:id==='B02'?'合成恒生科技ETF乙':'合成恒生科技ETF甲',quantity:id==='B02'?200:1000,cost_price:null,effective_at:'2026-01-01T00:00:00+08:00',reason:'用户提供的期初快照，合成验收'}}
     if(action==='commit_investment_change')args={preview_id:result('preview_investment_change').data.preview_id}
     if(action==='open_product_view')args={view:id==='B08'?'settings':id==='B01'?'investment':'notifications'}
     if(action==='resolve_research_scope')args={query:id==='B09'?'600519 行情条件跟进':'600519 财务摘要',mention_texts:['600519']}
     if(action==='confirm_research_entities'){const r=result('resolve_research_scope').data;args={snapshot_id:r.snapshot_id,version:r.version}}
     if(action==='query_market'&&id==='B14')args={operation:'quotes',confirmation_id:result('confirm_research_entities').confirmations[0].confirmation_id}
     if(action==='record_personalized_interaction')args={card_id:result('read_personalized_research').data.cards.cards[0].card_id,action:'analyze'}
     if(action==='review_research_decision')args={confirmation_id:result('confirm_research_entities').confirmations[0].confirmation_id,
      signal:{action:'买入',risk_score:.8,confidence:.4,target_price:null,reasoning:'明确合成的建议，只验收画像护栏；一份报价不足以形成真实投资结论。'},
      perspectives:[{role:'technical',summary:'只有明确合成报价，技术研究覆盖不足。',evidence_ids:[result('query_market').data.evidence_id]}]}
     if(action==='create_mandate'){const c=result('confirm_research_entities').confirmations[0];args={confirmation_id:c.confirmation_id,goal:'合成验收集合与提醒',scope:{entity_id:c.execution_entity_id,exchange:c.exchange,operation:'financial_summary',period:'20260630',metric:'营业总收入',basis:'source_abstract'},contact_note:'仅应用内，不发送外部通知'}}
     if(action==='create_mandate'&&id==='B09'){const c=result('confirm_research_entities').confirmations[0];args={confirmation_id:c.confirmation_id,goal:'合成验收：报价从90变为110时按条件联系',scope:{entity_id:c.execution_entity_id,exchange:c.exchange,operation:'market_quote'},contact_note:'仅应用内，不发送外部通知',contact_rule:{mode:'condition',condition:{type:'numeric',metric:'price',operator:'>=',threshold:100},notify_on:'transition',cooldown_minutes:0}}}
     if(action==='update_notification_preferences'){const c=result('read_notification_settings').data;args={expected_revision:c.revision,enabled:false,channels:['app'],timezone:'Asia/Shanghai',quiet_hours:{start:'22:00',end:'08:00'}}}
     if(action==='read_investment_collection')args={collection:'holdings'}
     if(action==='bind_mandate_investment_collection'){const m=result('list_mandates').data.items[0],c=result('read_investment_collection').data;args={mandate_id:m.mandate.mandate_id,collection:'holdings',mode:'fixed',expected_revision:m.mandate.current_revision,expected_generation:m.generation,expected_fact_version:c.fact_version}}
     if(action==='manage_mandate'){const m=result('list_mandates').data.items[0];args={mandate_id:m.mandate.mandate_id,action:'revise',expected_revision:m.mandate.current_revision,expected_generation:m.generation,definition:{goal:m.revision.goal,scope:m.revision.scope,contact_note:'每日北京时间09点应用内提醒；合成验收',reminder_time:'09:00',contact_channels:['app']}}}
    }else{
     const commit=result('commit_investment_change')||result('update_notification_preferences')||result('bind_mandate_investment_collection')||result('manage_mandate')||result('create_mandate')
     text=`${id} 合成回放完成。`+(id==='B10'||id==='B11'?'已核对风险偏好工具与投资档案回执。':commit?.saved===false?'你取消了本次操作，未保存。':commit?.ok?'业务服务已返回保存回执。':commit?'操作未完成，请核对工具错误。':id==='B08'?'入口已准备，请点击打开。':'已读取脱敏配置及真实投递列表。')
     if(id==='B16')text='B16 问答样式验收完成：原生单选、多选和自由填写正常返回；没有创建委托、提醒或交易。'
     const nav=result('open_product_view');if(nav?.navigation_required)text+=nav.guidance;if(nav?.url)text+=` [${nav.label}](${nav.url})`
     if(id==='B14'){
      const r=result('review_research_decision')?.data
      text=r?`B14 合成研究护栏回放完成。原建议：${r.original_signal.action}；校准后：${r.effective_signal?.action??'未知'}；护栏状态：${r.guard_status}。${r.guard_note??''} 研究覆盖：${r.coverage.status}；只有合成报价，其余视角缺材料。研究编号：${r.review_id}。read_research_reviews 已回查保存结果，没有创建委托、提醒或交易。`:'B14 未取得审查回执，请查看工具错误。'
     }
     if(id==='B15'){
      const r=result('record_personalized_interaction')?.data
      text=`B15 合成聊天学习入口回放完成：记录${r?.stored??'未知'}条，忽略${r?.ignored??'未知'}条。复用同一学习开关与现有卡片；当前暂停不会开启学习或新增兴趣事件。没有修改风险偏好、委托或交易。`
     }
    }
    await appendFile(process.env.HUOHUO_SKILLS_PROOF!,JSON.stringify({case:id,step,call:name||null,status:name?'stepping':'completed',session:options.sessionId})+'\n')
   }
   if(name){const id=ToolCallId('business-'+crypto.randomUUID()),argumentsText=JSON.stringify(args);yield {type:'block-start',index:0,blockType:'tool-call'};yield {type:'tool-call-delta',index:0,id,name,argumentsDelta:argumentsText};yield {type:'block-end',index:0,block:{type:'tool-call',id,name,arguments:argumentsText}};yield {type:'finish',reason:{kind:'tool-calls'}};return}
   yield {type:'block-start',index:0,blockType:'text'};yield {type:'text-delta',index:0,text};yield {type:'block-end',index:0,block:{type:'text',text}};yield {type:'finish',reason:{kind:'stop'}}
  }
 }
 ctx.llm.registerAdapter(['huohuo-skills-fixture'],new Fixture())
}
