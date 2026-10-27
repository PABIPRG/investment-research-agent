import type { ToolDefinition } from '@deepseek-ai/dsh-tools'
import { createHash } from 'node:crypto'
import {confirmBusiness,cancelled,channelsField,validate,type Ask} from './business-tools.js'
export const mandateToolNames=['resolve_research_scope','search_securities','create_mandate','list_mandates','get_mandate','manage_mandate']
const scope={type:'object',properties:{entity_id:{type:'string'},exchange:{type:'string',enum:['SSE','SZSE']},operation:{type:'string',enum:['quote_snapshot','company_profile','financial_summary']},period:{type:'string',description:'内部参数：将用户确认的自然语言报告期转换为8位日期，例如2026年半年报对应20260630。不要向用户要求YYYYMMDD格式；年份不明先澄清。'},metric:{type:'string',description:'内部参数：将用户想了解的收入或利润等指标核对为来源支持的指标名，不要求用户填写接口原名，不猜测不支持的指标。'},basis:{type:'string',enum:['source_abstract'],description:'内部固定值，由Agent填写；不要展示枚举或让用户选择。用户文案可说按数据来源提供的财务摘要展示，未知口径仍需说明。'}},required:['entity_id','exchange','operation'],additionalProperties:false}
const contactCondition={type:'object',properties:{type:{type:'string',enum:['semantic','numeric'],description:'semantic：需要用证据判断的变化；numeric：用户明确说出单点数值阈值，仅报价类委托可用。'},claim:{type:'string',minLength:1,maxLength:80,description:'语义条件：用户明确说出的单一可判定变化，用一句短语表达，例如“公告出现重大资产重组”。只写用户实际约定，不添加阈值或推断项。'},expected:{type:'string',enum:['met'],description:'固定为 met：只有条件满足时才联系。'},min_confidence:{type:'number',minimum:0,maximum:1,description:'可选，用户明确要求高把握才提醒时填写，不自行设定。'},metric:{type:'string',enum:['price','change','change_percent'],description:'数值条件指标：price 最新价（元/股）、change 相对昨收涨跌额（元）、change_percent 涨跌幅（%）。只填用户明确提到的指标，不自行换算。'},operator:{type:'string',enum:['>','>=','<','<=','==','!='],description:'数值条件比较符，按用户原话选择。'},threshold:{type:'number',description:'数值条件的阈值，必须是用户明确给出的数字，不猜测。'},unit:{type:'string',enum:['CNY/share','CNY','%'],description:'可省略，由程序按指标填写。'}},required:[],additionalProperties:false,description:'可选：仅当用户明确提出可判定的持续联系条件时填写；不填写则按“有重要变化才联系”。semantic 需要 claim；numeric 只支持报价类的 price、change、change_percent 单点阈值，需要用户明确说出数字，数值由程序从报价快照核对。均线、回撤、估值分位暂不支持，不要承诺。'}
export function createMandateTools(address:string,token:string,ask?:Ask):ToolDefinition[]{
  const specs:[string,string,Record<string,unknown>][]=[
    ['resolve_research_scope','解析用户原文中的名称、代码、目录别名、多个对象和本会话已确认指代；调用 confirm_research_entities 完成结构化选项确认。未知必须追问；解析不创建委托。',{query:{type:'string',maxLength:2000},mention_texts:{type:'array',items:{type:'string'},maxItems:12,description:'可选：抽取用户原文中的全部对象提及（含简称、未知对象），每项必须是原文片段；程序检索候选，禁止填造代码。'}}],
    ['search_securities','按股票名称或代码搜索沪深 A 股，例如科士达。这是补充搜索，不是确认记录；使用 resolve_research_scope 和 confirm_research_entities 保存实体确认，不要求用户先找代码。即使唯一匹配也需确认。ok 才可供确认；empty 表示未命中，unavailable/stale 表示来源失败，不可说股票不存在。只读搜索不会创建研究、委托或自选。',{query:{type:'string',minLength:1,maxLength:100,description:'提取用户要查的股票名称或代码关键词，不传整段意图'}}],
    ['create_mandate','仅在用户明确委托且确认证券代码及范围后创建持续委托。普通提问/加入自选不创建。当前执行初次报价、公司资料或明确期间指标的财务摘要研究；财务摘要与公司资料变化每 30 分钟/6 小时自动检查，报价在沪深交易时段每 15 分钟自动检查。用户明确说出可判定的持续联系条件时可填 contact_condition：语义条件需要 claim；报价类可用用户明确给出的数值阈值（price、change、change_percent），数值由程序核对。均线、回撤、分位不支持，不得把口述指标写进备注后声称已在跟踪。通知默认关闭，需用户在消推配置中开启后才会实际提醒。',{confirmation_id:{type:'string',description:'confirm_research_entities 保存并返回的有效确认编号，不得编造'},goal:{type:'string',minLength:1,maxLength:4000},scope,contact_note:{type:'string',minLength:1,maxLength:1000},contact_condition:contactCondition}],
    ['list_mandates','查询本人的真实持续委托列表、研究进展和基准。',{}],
    ['get_mandate','读取真实委托详情、版本、代次、结果和证据。',{mandate_id:{type:'string'}}],
    ['manage_mandate','用户明确要求时修改、暂停、恢复或结束委托。先读取详情，将当前版本/代次原样提交。修改必须包含完整目标、固定范围和约定，其余操作不传 definition。',{mandate_id:{type:'string'},action:{type:'string',enum:['pause','resume','end','revise']},expected_revision:{type:'integer',minimum:1},expected_generation:{type:'integer',minimum:0},definition:{type:'object',properties:{confirmation_id:{type:'string',description:'改变研究对象时必填本会话的有效确认编号'},goal:{type:'string'},scope,contact_note:{type:'string'},contact_condition:contactCondition,reminder_time:{type:['string','null'],pattern:'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$',description:'明确的每日北京时间提醒；null 关闭每日提醒，省略保留。'},contact_channels:channelsField},additionalProperties:false}}],
  ]
  return specs.map(([name,description,properties])=>({name,description,parameters:{type:'object',properties,required:Object.keys(properties).filter(k=>k!=='definition'&&k!=='mention_texts'&&k!=='contact_condition'),additionalProperties:false},output:{schema:{type:'object',additionalProperties:true},render:(_args,value)=>[{type:'text',text:JSON.stringify(value)}]},timeoutMs:name==='manage_mandate'?2147483000:30000,
    async execute(input,exec){
      validate({type:'object',properties,required:Object.keys(properties).filter(k=>k!=='definition'&&k!=='mention_texts'&&k!=='contact_condition'),additionalProperties:false},input)
      const args=input as any
      if(!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(properties,k)))throw new Error('参数无效')
      const session=exec.agent?.session.id;if(!session||!exec.callId)throw new Error('缺少可信会话')
      const key='chat:'+createHash('sha256').update(JSON.stringify([session,exec.callId,name])).digest('hex')
      let path='/mandates',body:any
      if(name==='search_securities'){path='/entities/search';body={query:args.query}}
      else if(name==='resolve_research_scope'){path='/entities/resolve';body={query:args.query,session_id:session,...(args.mention_texts!==undefined?{mention_texts:args.mention_texts}:{})}}
      else if(name==='create_mandate')body={...args,request_key:key,session_id:session}
      else if(name!=='list_mandates'){
        if(!/^MND_[a-f0-9]{32}$/.test(args.mandate_id))throw new Error('请先查询有效委托 ID')
        path+='/'+args.mandate_id
        if(name==='manage_mandate'){
          if(!['pause','resume','end','revise'].includes(args.action))throw new Error('不支持的操作')
          path+='/'+args.action
          if(args.action!=='revise'&&args.definition!==undefined)throw new Error('生命周期操作不能修改定义')
          body={session_id:session,request_key:key,expected_revision:args.expected_revision,expected_generation:args.expected_generation,...(args.action==='revise'?args.definition:{})}
        }
      }
      if(name==='manage_mandate'&&args.action==='revise'&&args.definition&&('contact_channels' in args.definition||'reminder_time' in args.definition||'contact_condition' in args.definition)){
        const labels:Record<string,string>={app:'应用内',wecom:'企业微信',serverchan:'Server 酱',email:'邮件'}
        const metricLabels:Record<string,string>={price:'最新价（元）',change:'涨跌额（元）',change_percent:'涨跌幅（%）'}
        const d=args.definition
        const cc=d.contact_condition
        const conditionText=!cc?'重要变化':cc.type==='numeric'?`${metricLabels[cc.metric]||cc.metric} ${cc.operator} ${cc.threshold}`:(cc.claim||'重要变化')
        if(!await confirmBusiness(ask,exec,`修改委托约定？目标：${d.goal}。联系备注：${d.contact_note}。联系条件：${conditionText}。每日提醒：${d.reminder_time===null?'关闭':d.reminder_time===undefined?'保持原值':d.reminder_time+'（北京时间，每日）'}。联系渠道：${d.contact_channels?.map((x:string)=>labels[x]).join('、')||'保持原值'}。产生新版本并撤销旧执行资格；选择外部渠道会允许该委托按约发送，已在途请求无法撤回。`))return cancelled
      }
      try{const response=await fetch(new URL(path,address),{method:body?'POST':'GET',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,redirect:'error',signal:AbortSignal.any([exec.signal,AbortSignal.timeout(25000)])});const data=await response.json();return {ok:response.ok,http_status:response.status,data,request_key:key}}
      catch{return {ok:false,error:name==='search_securities'||name==='resolve_research_scope'?'backend_unavailable':body?'submission_unknown':'backend_unavailable',request_key:key,guidance:'先查询核对，不要自动创建另一项委托。'}}
    }
  }))
}
