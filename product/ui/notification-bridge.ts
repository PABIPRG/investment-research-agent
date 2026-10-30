/** Fixed owner-authenticated routes. Browser input never selects a Host, principal or secret. */
export const notificationPaths = [
  '/api/huohuo/notification-config',
  '/api/huohuo/notifications',
  '/api/huohuo/notification-tests',
  '/api/huohuo/notification-test-command',
  '/api/huohuo/app-notifications',
]
export function createNotificationBridge(address: string, token: string) {
  const base = new URL(address)
  if (
    base.protocol !== 'http:' ||
    base.hostname !== '127.0.0.1' ||
    !base.port ||
    base.pathname !== '/' ||
    base.username ||
    base.password ||
    base.search ||
    base.hash ||
    !token
  )
    throw new Error('消推 API 配置无效')
  return async (request: Request) => {
    const reply = (status: number, value: unknown) =>
      Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    let path = '',
      body: string | undefined,
      sending = false
    const config = url.pathname === notificationPaths[0]
    if (url.search || !notificationPaths.includes(url.pathname))
      return reply(405, { detail: '不支持的请求' })
    if (request.method === 'GET') {
      path = config
        ? '/notifications/config'
        : url.pathname === notificationPaths[1]
          ? '/notifications'
          : url.pathname === notificationPaths[2]
            ? '/notifications/tests'
            : url.pathname === notificationPaths[4]
              ? '/notifications/in-app'
              : ''
      if (!path) return reply(405, { detail: '不支持的请求' })
    } else if (request.method === 'POST' && (config || url.pathname === notificationPaths[3])) {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
        return reply(400, { detail: '需要 JSON 请求' })
      const raw = await request.text()
      if (raw.length > 12000) return reply(400, { detail: '请求过大' })
      let value: any
      try {
        value = JSON.parse(raw)
      } catch {
        return reply(400, { detail: '无效请求' })
      }
      if (config) {
        path = '/notifications/config'
        body = raw
      } else {
        if (
          !value ||
          typeof value !== 'object' ||
          Array.isArray(value) ||
          'session_id' in value ||
          !['prepare', 'send', 'inspect', 'cancel'].includes(value.operation)
        )
          return reply(400, { detail: '测试操作无效' })
        const { operation, ...payload } = value
        path = '/notifications/tests/' + operation
        sending = operation === 'send'
        body = JSON.stringify({ ...payload, session_id: 'ui-notification-owner' })
      }
    } else return reply(405, { detail: '不支持的请求' })
    try {
      const response = await fetch(new URL(path, base), {
        method: request.method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body,
        redirect: 'error',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(sending ? 35000 : 10000)]),
      })
      return reply(response.status, await response.json())
    } catch {
      return reply(503, {
        detail: sending
          ? '发送结果未知。请核对测试记录，不要重复提交。'
          : body
            ? '连接中断，请先刷新核对记录。'
            : '后台暂时不可用，请重试。',
      })
    }
  }
}
