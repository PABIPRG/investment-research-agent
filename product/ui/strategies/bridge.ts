/** Owner-authenticated transport, fixed commands and server-owned UI session. */
export const strategyPaths = ['/api/huohuo/strategies', '/api/huohuo/strategy-command']
export function createStrategyBridge(address: string, token: string) {
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
    throw Error('策略 API 配置无效')
  return async (request: Request): Promise<Response> => {
    const reply = (status: number, value: unknown) =>
      Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    let path = '/strategies',
      body: any
    if (request.method === 'GET' && url.pathname === strategyPaths[0] && !url.search) {
    } else if (request.method === 'POST' && url.pathname === strategyPaths[1] && !url.search) {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
        return reply(400, { detail: '需要 JSON 请求' })
      const raw = await request.text()
      if (raw.length > 20000) return reply(400, { detail: '请求过大' })
      try {
        body = JSON.parse(raw)
      } catch {
        return reply(400, { detail: '请求格式无效' })
      }
      if (
        !body ||
        typeof body !== 'object' ||
        Array.isArray(body) ||
        !['prepare', 'commit', 'cancel'].includes(body.operation) ||
        'session_id' in body
      )
        return reply(400, { detail: '操作无效' })
      const { operation, ...payload } = body
      path += '/' + operation
      body = operation === 'cancel' ? payload : { ...payload, session_id: 'ui-strategy-owner' }
    } else return reply(405, { detail: '不支持的请求' })
    try {
      const r = await fetch(new URL(path, base), {
        method: body ? 'POST' : 'GET',
        redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(body ? 115000 : 15000)]),
      })
      const raw = await r.text()
      if (raw.length > 4_000_000) return reply(502, { detail: '结果过大，请缩小查询范围' })
      return reply(r.status, JSON.parse(raw))
    } catch {
      return reply(503, {
        detail: body
          ? '连接中断，本次操作可能已接受。请先刷新运行记录核对，勿重复提交。'
          : '策略记录暂时无法读取，请重试。',
      })
    }
  }
}
