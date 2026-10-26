import test from 'node:test'
import assert from 'node:assert/strict'
import {createInvestmentTools} from '../product/chat/investment-tools.js'
const exec={agent:{session:{id:'session-a'}},callId:'call-a',signal:new AbortController().signal} as any
const preview={preview_id:'00000000-0000-4000-8000-000000000001',fact_version:0,command:'holding',payload:{ticker:'513130',name:'合成恒生科技ETF',quantity:1000,cost_price:null},before:{holdings:[],watchlist:[]},after:{holdings:[{ticker:'513130',quantity:1000,cost_price:null}],watchlist:[]},impact:{}}
const selected={answers:[{id:'business-confirm',selected:['确认执行']}]}
test('投资提交必须显示服务端预览并取得真实选择，跳过/文字/伪造均不写',async()=>{
 const original=globalThis.fetch
 try{
  let posts=0
  globalThis.fetch=async(_url,init)=>{if(init?.method==='POST')posts++;return Response.json(preview)}
  for(const answer of [{pending:true},{answers:[]},{answers:[{id:'business-confirm',selected:['确认执行'],custom:'随便'}]},{answers:[{id:'business-confirm',selected:['确认执行','取消']}]},{answers:[{id:'business-confirm',selected:['确认执行']},{id:'business-confirm',selected:['确认执行']}]}]){
   const tools=(createInvestmentTools as any)('http://127.0.0.1:18930','test',async()=>answer)
   const t=tools.find((t:any)=>t.name==='commit_investment_change');assert.ok(t,'缺少持仓写入 Tool')
   const result=await t.execute({preview_id:preview.preview_id},exec);assert.equal(result.saved,false)
  }
  assert.equal(posts,0)
 }finally{globalThis.fetch=original}
})
test('确认后只提交预览身份，稳定幂等；已保存不重复提问',async()=>{
 const original=globalThis.fetch
 try{
  const sent:any[]=[];let questions:any[]=[];let saved=false
  const receipt={saved:true,facts:{version:1,holdings:preview.after.holdings}}
  globalThis.fetch=async(_url,init)=>{if(init?.method==='POST'){sent.push(JSON.parse(String(init.body)));saved=true;return Response.json(receipt)}return Response.json(saved?{...preview,receipt}:preview)}
  const tools=(createInvestmentTools as any)('http://127.0.0.1:18930','test',async(q:any[])=>{questions=q;return selected})
  const t=tools.find((t:any)=>t.name==='commit_investment_change');assert.ok(t)
  assert.equal((await t.execute({preview_id:preview.preview_id},exec)).data.saved,true)
  assert.match(questions[0].question,/513130/)
  assert.match(questions[0].question,/1000/)
  assert.deepEqual(sent,[{preview_id:preview.preview_id,request_key:preview.preview_id}])
  questions=[];assert.equal((await t.execute({preview_id:preview.preview_id},{...exec,callId:'retry'})).data.saved,true)
  assert.deepEqual(questions,[]);assert.equal(sent.length,1)
 }finally{globalThis.fetch=original}
})

test('预览冲突不询问不写，提交中断保留未知并禁止自动重试',async()=>{
 const original=globalThis.fetch
 try{
  let asked=0,posts=0
  const tool=(createInvestmentTools as any)('http://127.0.0.1:18930','test',async()=>{asked++;return selected}).find((t:any)=>t.name==='commit_investment_change')
  globalThis.fetch=async()=>Response.json({detail:'版本冲突'},{status:409})
  assert.equal((await tool.execute({preview_id:preview.preview_id},exec)).http_status,409);assert.equal(asked,0)
  globalThis.fetch=async(_url,init)=>{if(init?.method==='POST'){posts++;throw new Error('offline')}return Response.json(preview)}
  assert.equal((await tool.execute({preview_id:preview.preview_id},exec)).error,'submission_unknown');assert.equal(posts,1)
  await assert.rejects(tool.execute({preview_id:preview.preview_id,confirmed:true},exec),/未允许字段/)
  assert.equal(posts,1)
 }finally{globalThis.fetch=original}
})

import {createNotificationTools} from '../product/chat/notification-tools.js'
import {createMandateTools} from '../product/chat/mandate-tools.js'
import {parseProductLink} from '../product/ui/navigation.js'
const config={revision:2,enabled:false,channels:['app'],timezone:'Asia/Shanghai',quiet_hours:null,external:{wecom:{configured:true,secret_saved:{key:true},key:'secret-never-return'}},external_status:'仅配置'}
test('通知脱敏、取消不写、版本冲突不覆盖、额外秘密字段拒绝',async()=>{
 const original=globalThis.fetch
 try{
  let writes=0;globalThis.fetch=async(_url,init)=>{if(init?.method==='POST')writes++;return Response.json(config)}
  const tools=createNotificationTools('http://127.0.0.1:18930','test',async()=>({answers:[]}))
  const read=await tools[0].execute({},exec);assert.ok(!JSON.stringify(read).includes('secret-never-return'))
  const args={expected_revision:2,enabled:true,channels:['app'],timezone:'Asia/Shanghai',quiet_hours:{start:'22:00',end:'08:00'}}
  assert.equal((await tools[2].execute(args,exec) as any).saved,false)
  assert.equal((await tools[2].execute({...args,expected_revision:1},exec) as any).ok,false)
  await assert.rejects(tools[2].execute({...args,external:{wecom:{key:'unsafe'}}},exec),/未允许字段/)
  assert.equal(writes,0)
 }finally{globalThis.fetch=original}
})
test('通知确认提交保留 revision，渠道清除只提交指定渠道',async()=>{
 const original=globalThis.fetch
 try{
  let body:any;globalThis.fetch=async(_u,init)=>{if(init?.body)body=JSON.parse(String(init.body));return Response.json(config)}
  const tools=createNotificationTools('http://127.0.0.1:18930','test',async()=>selected)
  const args={expected_revision:2,enabled:true,channels:['app'],timezone:'Asia/Shanghai',quiet_hours:null}
  assert.equal((await tools[2].execute(args,exec) as any).ok,true);assert.deepEqual(body,args)
  await tools[3].execute({channel:'wecom',expected_revision:2},exec)
  assert.deepEqual((body as any).external,{wecom:{clear:true}});assert.deepEqual(body.channels,['app'])
 }finally{globalThis.fetch=original}
})
test('集合关联从真实范围确认，校验版本；委托提醒渠道字段穿透原服务',async()=>{
 const original=globalThis.fetch
 try{
  const mid='MND_'+'a'.repeat(32);let body:any
  const view={mandate:{current_revision:3,status:'paused'},generation:4,revision:{goal:'合成研究'}}
  globalThis.fetch=async(url,init)=>{if(String(url).endsWith('/collection'))return Response.json({fact_version:2,status:'ready',members:[{name:'合成ETF',entity_id:'FUND:CN:513130'}]});if(init?.body)body=JSON.parse(String(init.body));return Response.json(view)}
  const tools=createInvestmentTools('http://127.0.0.1:18930','test',async()=>selected)
  const args={mandate_id:mid,collection:'holdings',mode:'fixed',expected_revision:3,expected_generation:4,expected_fact_version:2}
  assert.equal((await tools[4].execute(args,exec) as any).ok,true);assert.equal(body.mode,'fixed');assert.match(body.request_key,/^chat:/)
  body=undefined;assert.equal((await tools[4].execute({...args,expected_fact_version:1},exec) as any).ok,false);assert.equal(body,undefined)
  const manage=createMandateTools('http://127.0.0.1:18930','test',async()=>selected).find(t=>t.name==='manage_mandate')!
  await manage.execute({mandate_id:mid,action:'revise',expected_revision:3,expected_generation:4,definition:{goal:'合成',scope:{entity_id:'SEC:CN:A:600519',exchange:'SSE',operation:'quote_snapshot'},contact_note:'每天提醒',reminder_time:'09:00',contact_channels:['app']}},exec)
  assert.equal((body as any).reminder_time,'09:00');assert.deepEqual((body as any).contact_channels,['app'])
 }finally{globalThis.fetch=original}
})
test('导航仅接受已知视图和合法委托标识，拒绝重复或任意参数',()=>{
 assert.deepEqual(parseProductLink('#huohuo-view=investment'),{view:'investment',mandate:null})
 for(const hash of ['#huohuo-view=https://evil.test','#huohuo-view=investment&url=/etc','#huohuo-view=investment&huohuo-view=chat','#huohuo-view=chat&mandate=MND_'+ 'a'.repeat(32),'#huohuo-view=mandates&mandate=../other'])assert.equal(parseProductLink(hash),null)
})

import {createNavigationTools} from '../product/chat/navigation-tools.js'
test('页面链接使用运行实例来源，设置没有公开 API 时给出准确入口',async()=>{
 const tool=createNavigationTools('http://127.0.0.1:18930','test','http://127.0.0.1:18931')[0]
 const r=await tool.execute({view:'investment'},exec) as any
 assert.equal(r.url,'http://127.0.0.1:18931/#huohuo-view=investment')
 const settings=await tool.execute({view:'settings'},exec) as any
 assert.equal(settings.navigation_required,true);assert.equal(settings.url,undefined);assert.match(settings.guidance,/设置.*模型/)
 assert.equal(parseProductLink('#huohuo-view=settings'),null)
})
test('委托参数不能覆盖可信会话或注入不允许的嵌套字段',async()=>{
 const t=createMandateTools('http://127.0.0.1:18930','test',async()=>{throw Error('不应问确认')}).find(t=>t.name==='manage_mandate')!
 await assert.rejects(t.execute({mandate_id:'MND_'+'a'.repeat(32),action:'revise',expected_revision:1,expected_generation:0,definition:{session_id:'forged',contact_channels:['app']}},exec),/未允许字段/)
})
