import test from 'node:test'
import assert from 'node:assert/strict'
import {createStrategyTools,strategyConfirmed} from '../product/chat/strategy-tools.js'
import {createStrategyBridge} from '../product/ui/strategies/bridge.js'
const approved={answers:[{id:'strategy-confirm',selected:['确认执行']}]}
test('策略确认只接受原生单选；自由回答/跳过/伪造不提交',()=>{
 assert.equal(strategyConfirmed(approved),true)
 for(const a of [null,{}, {answers:[]},{answers:[{id:'strategy-confirm',custom:'确认执行',selected:['确认执行']}]},{answers:[{id:'strategy-confirm',selected:['确认执行','暂不执行']}]},{answers:[{id:'wrong',selected:['确认执行']}]}])assert.equal(strategyConfirmed(a),false)
})
test('策略工具先预览再等原生回答；取消不commit，可信身份不能覆盖',async()=>{
 const previous=globalThis.fetch;const seen:any[]=[]
 globalThis.fetch=async(url:any,init:any)=>{seen.push({url:String(url),body:JSON.parse(init.body)});return Response.json(String(url).endsWith('/prepare')?{preview_id:'private-preview',request_key:'unused',summary:'受控策略范围'}:{run:{status:'completed'}})}
 const exec={agent:{session:{id:'trusted-session'}},callId:'call-1',signal:new AbortController().signal} as any
 try{
  const cancel=createStrategyTools('http://127.0.0.1:18840','fixture',async()=>({answers:[]}))[1]
  assert.equal((await cancel.execute({action:'create',payload:{}},exec) as any).status,'cancelled')
  assert.equal(seen.length,1);assert.equal(seen[0].body.session_id,'trusted-session')
  const ok=createStrategyTools('http://127.0.0.1:18840','fixture',async()=>approved)[1]
  await ok.execute({action:'create',payload:{}},exec)
  assert.equal(seen.length,3);assert.ok(seen[2].url.endsWith('/commit'))
  assert.equal(seen[1].body.request_key,seen[2].body.request_key)
  await assert.rejects(ok.execute({action:'create',payload:{},session_id:'forged'},exec))
  assert.equal(seen.length,3)
 }finally{globalThis.fetch=previous}
})
test('页面桥限定路径与身份；提交失败明确保留未知，不自动重试',async()=>{
 const previous=globalThis.fetch;const seen:any[]=[]
 globalThis.fetch=async(url:any,init:any)=>{seen.push({url:String(url),body:JSON.parse(init.body)});throw Error('network')}
 try{
  const bridge=createStrategyBridge('http://127.0.0.1:18840','fixture')
  const r=await bridge(new Request('http://local/api/huohuo/strategy-command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'commit',preview_id:'x',request_key:'k'})}))
  assert.equal(r.status,503);assert.match((await r.json()).detail,/可能已接受/)
  assert.equal(seen.length,1);assert.equal(seen[0].body.session_id,'ui-strategy-owner')
  const bad=await bridge(new Request('http://local/api/huohuo/strategy-command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'commit',session_id:'forged'})}))
  assert.equal(bad.status,400);assert.equal(seen.length,1)
 }finally{globalThis.fetch=previous}
})
