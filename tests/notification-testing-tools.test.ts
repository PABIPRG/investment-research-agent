import test from 'node:test'
import assert from 'node:assert/strict'
import {createNotificationTools} from '../product/chat/notification-tools.js'
import {createNotificationBridge} from '../product/ui/notification-bridge.js'
const exec={agent:{session:{id:'trusted-chat'}},callId:'test-call',signal:new AbortController().signal} as any
const prepared={test_id:'NTT_'+'a'.repeat(32),request_key:'server-request',channel:'wecom',target_summary:'已保存的企业微信机器人',status:'prepared',ignores_quiet_hours:true}
const answer={answers:[{id:'business-confirm',selected:['确认执行']}]}
test('测试提醒的最终确认读取服务端目标；取消/跳过不发送，秘密及目标参数拒绝',async()=>{
 const old=globalThis.fetch;let sends=0;let question=''
 try{
  globalThis.fetch=async(u)=>{if(String(u).endsWith('/send'))sends++;return Response.json(prepared)}
  const tools=createNotificationTools('http://127.0.0.1:18000','fixture',async(q)=>{question=JSON.stringify(q);return {answers:[]}})
  const send=tools.find(t=>t.name==='send_notification_test')!
  assert.equal((await send.execute({test_id:prepared.test_id},exec) as any).saved,false)
  assert.equal(sends,0);assert.match(question,/忽略静默/);assert.match(question,/已保存的企业微信机器人/)
  await assert.rejects(send.execute({test_id:prepared.test_id,destination:'other'},exec),/未允许字段/)
  const prepare=tools.find(t=>t.name==='prepare_notification_test')!
  await assert.rejects(prepare.execute({channel:'wecom',expected_revision:1,key:'secret'},exec),/未允许字段/)
 }finally{globalThis.fetch=old}
})
test('聊天发送使用可信会话与服务端请求身份，已提交/未知不重问或重发',async()=>{
 const old=globalThis.fetch;let asks=0;let body:any;let status='prepared'
 try{
  globalThis.fetch=async(u,init)=>{if(String(u).endsWith('/send'))body=JSON.parse(String(init?.body));return Response.json({...prepared,status})}
  const t=createNotificationTools('http://127.0.0.1:18000','fixture',async()=>{asks++;return answer}).find(t=>t.name==='send_notification_test')!
  await t.execute({test_id:prepared.test_id},exec)
  assert.equal(asks,1);assert.equal(body.session_id,'trusted-chat');assert.equal(body.request_key,'server-request')
  status='unknown';body=undefined
  assert.equal((await t.execute({test_id:prepared.test_id},exec) as any).submitted,false)
  assert.equal(asks,1);assert.equal(body,undefined)
 }finally{globalThis.fetch=old}
})
test('页面桥只开放固定操作并注入实例UI会话，发送中断不建议重发',async()=>{
 const old=globalThis.fetch;let captured:any
 const bridge=createNotificationBridge('http://127.0.0.1:18000','fixture')
 const req=(body:any)=>new Request('http://localhost/api/huohuo/notification-test-command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})
 try{
  globalThis.fetch=async(u,init)=>{captured={url:String(u),body:JSON.parse(String(init?.body))};return Response.json(prepared)}
  assert.equal((await bridge(req({operation:'prepare',channel:'wecom',expected_revision:1,request_key:'one'}))).status,200)
  assert.equal(captured.url,'http://127.0.0.1:18000/notifications/tests/prepare');assert.equal(captured.body.session_id,'ui-notification-owner')
  assert.equal((await bridge(req({operation:'send',session_id:'forged'}))).status,400)
  assert.equal((await bridge(req({operation:'https://other.invalid'}))).status,400)
  globalThis.fetch=async()=>{throw Error('private-transmission-error')}
  const response=await bridge(req({operation:'send',test_id:prepared.test_id,request_key:'one'}))
  const text=await response.text();assert.equal(response.status,503);assert.match(text,/结果未知/);assert.match(text,/不要重复/);assert.ok(!text.includes('private-transmission'))
 }finally{globalThis.fetch=old}
})
