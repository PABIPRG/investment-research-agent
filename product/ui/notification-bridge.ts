/** Fixed owner-authenticated transport. No arbitrary URL, principal or transport credential from UI; channel configuration is owner-authenticated. */
export const notificationPaths = ['/api/huohuo/notification-config', '/api/huohuo/notifications']
export function createNotificationBridge(address: string, token: string) {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/' || base.username || base.password || base.search || base.hash || !token) throw new Error('消推 API 配置无效')
  return async (request: Request) => {
    const reply = (status: number, value: unknown) => Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    if (url.search || !notificationPaths.includes(url.pathname) || !['GET','POST'].includes(request.method) || (request.method === 'POST' && url.pathname !== notificationPaths[0])) return reply(405, { detail: '不支持的请求' })
    let body: string | undefined
    if (request.method === 'POST') {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json') return reply(400, { detail: '需要 JSON 请求' })
      body = await request.text(); if (body.length > 12000) return reply(400, { detail: '配置过大' })
      try { JSON.parse(body) } catch { return reply(400, { detail: '无效配置' }) }
    }
    try {
      const response = await fetch(new URL(url.pathname === notificationPaths[0] ? '/notifications/config' : '/notifications', base), { method: request.method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body, redirect: 'error', signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]) })
      return reply(response.status, await response.json())
    } catch { return reply(503, { detail: body ? '连接中断，配置可能已保存。请刷新核对后重试。' : '后台暂时不可用，请重试。' }) }
  }
}
