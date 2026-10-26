import test from 'node:test'
import assert from 'node:assert/strict'
import { createNotificationBridge } from '../product/ui/notification-bridge.js'
test('通知桥限制本机地址和请求范围', async () => {
  assert.throws(()=>createNotificationBridge('https://example.com','token'))
  assert.throws(()=>createNotificationBridge('http://user@127.0.0.1:18610','token'))
  const bridge=createNotificationBridge('http://127.0.0.1:18610','test')
  assert.equal((await bridge(new Request('http://localhost/api/huohuo/notifications',{method:'POST'}))).status,405)
  assert.equal((await bridge(new Request('http://localhost/api/huohuo/notification-config?principal=other'))).status,405)
  assert.equal((await bridge(new Request('http://localhost/api/huohuo/notification-config',{method:'POST',body:'{}'}))).status,400)
})
