import test from 'node:test'
import assert from 'node:assert/strict'
import {createMandateTools} from '../product/chat/mandate-tools.js'
const args={confirmation_id:'confirmed-object',goal:'合成委托',scope:{entity_id:'SEC:CN:A:600519',exchange:'SSE',operation:'quote_snapshot'},contact_note:'应用内'}
const exec={agent:{session:{id:'chat'}},callId:'one-call',signal:new AbortController().signal} as any
const answer={answers:[{id:'business-confirm',selected:['确认执行']}]}
test('同一工具调用重入只弹一次保存授权、只提交一次，改定义拒绝，新调用仍须确认',async()=>{
 const original=globalThis.fetch;let asked=0,written=0
 try{
  globalThis.fetch=async()=>{written++;return Response.json({mandate:{mandate_id:'MND_'+'a'.repeat(32)}})}
  const tool=createMandateTools('http://127.0.0.1:18000','fixture',async()=>{asked++;return answer}).find(t=>t.name==='create_mandate')!
  const [a,b]=await Promise.all([tool.execute(args,exec),tool.execute(args,exec)])
  assert.deepEqual(a,b);assert.equal(asked,1);assert.equal(written,1)
  await assert.rejects(tool.execute({...args,goal:'其他目标'},exec),/不能改写/)
  await tool.execute({...args,goal:'其他目标'},{...exec,callId:'new-call'})
  assert.equal(asked,2);assert.equal(written,2)
 }finally{globalThis.fetch=original}
})
test('提交结果未知保留原结果，同一调用不重问、不重发；取消不写',async()=>{
 const original=globalThis.fetch;let asked=0,written=0
 try{
  globalThis.fetch=async()=>{written++;throw Error('offline')}
  const tool=createMandateTools('http://127.0.0.1:18000','fixture',async()=>{asked++;return answer}).find(t=>t.name==='create_mandate')!
  assert.equal((await tool.execute(args,exec) as any).error,'submission_unknown')
  assert.equal((await tool.execute(args,exec) as any).error,'submission_unknown')
  assert.equal(asked,1);assert.equal(written,1)
  const cancel=createMandateTools('http://127.0.0.1:18000','fixture',async()=>({answers:[]})).find(t=>t.name==='create_mandate')!
  assert.equal((await cancel.execute(args,exec) as any).saved,false);assert.equal(written,1)
 }finally{globalThis.fetch=original}
})
