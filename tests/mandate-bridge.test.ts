import test from 'node:test'
import assert from 'node:assert/strict'
import {createMandateBridge} from '../product/ui/mandate-bridge.js'
test('委托桥拒绝任意路径、主体字段不透传成身份、非法方法和ID',async()=>{
 const bridge=createMandateBridge('http://127.0.0.1:18586','test-token')
 for(const req of [new Request('http://localhost/api/huohuo/mandate?id=../worker/claim'),new Request('http://localhost/api/huohuo/mandates?url=evil'),new Request('http://localhost/api/huohuo/mandate-command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'pause',mandate_id:'../worker'})})]) assert.ok((await bridge(req)).status>=400)
 assert.throws(()=>createMandateBridge('http://evil.invalid','token'))
})
