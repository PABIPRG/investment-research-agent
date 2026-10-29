/** 固定本机偏好桥；不接受任意地址、主体或会话。 */
export const personalizationPath = '/api/huohuo/personalization'
export function createPersonalizationBridge(address: string, token: string) {
  const base = new URL(address)
  if (
    base.protocol !== 'http:' ||
    base.hostname !== '127.0.0.1' ||
    !base.port ||
    base.pathname !== '/' ||
    base.search ||
    base.hash ||
    base.username ||
    base.password ||
    !token
  )
    throw Error('偏好 API 配置无效')
  return async (request: Request) => {
    const reply = (status: number, data: unknown) =>
      Response.json(data, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    if (request.method !== 'POST' || url.pathname !== personalizationPath || url.search)
      return reply(405, { detail: '不支持的偏好请求' })
    try {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
        return reply(400, { detail: '需要 JSON 请求' })
      const raw = await request.text()
      if (raw.length > 20000) return reply(400, { detail: '请求过大' })
      const input = JSON.parse(raw)
      if (
        !input ||
        typeof input !== 'object' ||
        Array.isArray(input) ||
        'principal' in input ||
        'session_id' in input
      )
        return reply(400, { detail: '偏好字段无效' })
      const { operation, ...payload } = input
      if (
        !['read', 'preview', 'commit', 'record', 'inspect', 'refresh', 'risk'].includes(operation)
      )
        return reply(400, { detail: '偏好操作无效' })
      let path = '/personalization/' + operation,
        method = 'POST',
        body = payload
      if (operation === 'inspect') {
        if (
          Object.keys(payload).length !== 1 ||
          typeof payload.preview_id !== 'string' ||
          !/^[0-9a-f-]{36}$/.test(payload.preview_id)
        )
          return reply(400, { detail: '预览标识无效' })
        path = '/personalization/previews/' + payload.preview_id
        method = 'GET'
      }
      if (operation === 'record') body = { ...payload, session_id: 'product-personalization' }
      const response = await fetch(new URL(path, base), {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: method === 'POST' ? JSON.stringify(body) : undefined,
        redirect: 'error',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(15000)]),
      })
      return reply(response.status, await response.json())
    } catch {
      return reply(503, { detail: '偏好连接中断；写入结果待核对，请查询原预览回执。' })
    }
  }
}
