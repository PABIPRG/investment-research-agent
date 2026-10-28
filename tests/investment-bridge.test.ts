import test from 'node:test'
import assert from 'node:assert/strict'
import {createInvestmentBridge} from '../product/ui/investment-bridge.js'
import {createInvestmentTools} from '../product/chat/investment-tools.js'
test('投资桥只允许固定路由与操作',async()=>{
 const bridge=createInvestmentBridge('http://127.0.0.1:18620','test-token')
 for(const req of [new Request('http://localhost/api/huohuo/investment?principal=other'),new Request('http://localhost/api/huohuo/investment-command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'../worker/claim'})}),new Request('http://localhost/api/huohuo/investment',{method:'DELETE'})])assert.ok((await bridge(req)).status>=400)
 assert.throws(()=>createInvestmentBridge('https://example.invalid','x'))
})
test('投资事实读取工具读取统一事实，失败不等于空集合',async()=>{
 const original=globalThis.fetch
 try{
  globalThis.fetch=async()=>{throw new Error('offline')}
  const tool=createInvestmentTools('http://127.0.0.1:18620','test-token')[0]
  const result=await tool.execute({}, {agent:{session:{id:'test'}},callId:'read-test',signal:new AbortController().signal} as any)
  assert.deepEqual(result,{ok:false,error:'investment_read_failed'})
 }finally{globalThis.fetch=original}
})
