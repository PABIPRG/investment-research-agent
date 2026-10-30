import test from 'node:test'
import assert from 'node:assert/strict'
import {createNavigationTools} from '../product/chat/navigation-tools.js'
const exec={agent:{session:{id:'fixture'}},callId:'navigation',signal:new AbortController().signal} as any
async function link(origin?:string){return await createNavigationTools('http://127.0.0.1:18000','fixture',origin)[0].execute({view:'notifications'},exec) as any}
test('部署域名与站内相对入口不泄露回环地址，拒绝携带凭据或任意路径',async()=>{
 assert.equal((await link('https://huohuo.xiexin.dev')).url,'https://huohuo.xiexin.dev/#huohuo-view=notifications')
 assert.equal((await link('')).ok,false)
 for(const url of ['https://user:secret@example.test','https://example.test/?token=secret','https://example.test/path','http://example.test','javascript:alert(1)'])assert.equal((await link(url)).ok,false)
})

import {canonicalProductHref} from '../product/ui/navigation.js'
test('历史产品回环入口修正到当前域名，不改写任意本机资料链接或外部网页',()=>{
 const base='https://huohuo.xiexin.dev/'
 assert.equal(canonicalProductHref('http://127.0.0.1:18979/#huohuo-view=notifications',base),base+'#huohuo-view=notifications')
 assert.equal(canonicalProductHref('http://127.0.0.1:18979/report',base),'http://127.0.0.1:18979/report')
 assert.equal(canonicalProductHref('https://source.example/report',base),'https://source.example/report')
 assert.equal(canonicalProductHref('http://[invalid',base),'http://[invalid')
 assert.equal(canonicalProductHref('/#huohuo-view=investment',base),base+'#huohuo-view=investment')
})

test('延迟读取DSH公开入口，避免工具注册时捕获旧监听地址',async()=>{
 let advertised='http://127.0.0.1:18942'
 const tool=createNavigationTools('http://127.0.0.1:18000','fixture',()=>advertised)[0]
 advertised='https://huohuo.xiexin.dev/'
 const result=await tool.execute({view:'notifications'},exec) as any
 assert.equal(result.url,'https://huohuo.xiexin.dev/#huohuo-view=notifications')
})
