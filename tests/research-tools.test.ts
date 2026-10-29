import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createResearchTools, retiredResearchToolNames } from '../product/tools/research-tools.js'
import { researchToolCatalog } from '../product/tools/research-tools.generated.js'
import { allowedChatToolNames } from '../product/chat/tools.js'

test('63 个生效 DSH 研究工具通过统一桥传递可信身份，禁止模型覆盖', async () => {
 const seen:any[]=[]
 const server=createServer(async(req,res)=>{let body='';for await(const chunk of req)body+=chunk;seen.push({path:req.url,auth:req.headers.authorization,body:JSON.parse(body)});res.setHeader('Content-Type','application/json');res.end(JSON.stringify({status:'ok',evidence_id:'fixture'}))})
 await new Promise<void>(r=>server.listen(Number(process.env.HUOHUO_CHAT_TEST_PORT ?? 0),'127.0.0.1',r))
 try {
  const port=(server.address() as any).port;const tools=createResearchTools(`http://127.0.0.1:${port}`,'test-token')
  assert.equal(tools.length,63);assert.equal(new Set(tools.map(t=>t.name)).size,63)
  assert.equal(researchToolCatalog.length,67)
  for(const name of retiredResearchToolNames)assert.ok(!tools.some(t=>t.name===name)&&!allowedChatToolNames.includes(name))
  for(const tool of tools){
   assert.ok(allowedChatToolNames.includes(tool.name))
   const schema=tool.parameters as any;const args:any={}
   for(const name of schema.required)args[name]=name==='confirmation_id'?'confirmed':name==='report_id'?'AP202610280000001234':'政策'
   await tool.execute(args,{agent:{session:{id:'trusted-session'}},callId:'call-'+tool.name,signal:new AbortController().signal} as any)
  }
  assert.equal(seen.length,63)
  for(const request of seen){assert.equal(request.path,'/research-tools/run');assert.equal(request.auth,'Bearer test-token');assert.equal(request.body.session_id,'trusted-session');assert.ok(request.body.call_id.startsWith('call-'))}
  await assert.rejects(tools[0].execute({authorized:true},{agent:{session:{id:'trusted-session'}},callId:'forged'} as any))
  assert.equal(seen.length,63)
 }finally{await new Promise<void>((resolve,reject)=>server.close(e=>e?reject(e):resolve()))}
})
