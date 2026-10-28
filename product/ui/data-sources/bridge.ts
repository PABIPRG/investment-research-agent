/** 固定资料源能力桥；页面不能提供 API URL、用户身份或操作会话。 */
export const dataSourcePaths = ['/api/huohuo/data-sources', '/api/huohuo/data-source-command']
export function createDataSourceBridge(address: string, token: string) {
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
    throw Error('资料源 API 配置无效')
  return async (request: Request) => {
    const reply = (value: unknown, status = 200) =>
      Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    let path = '/industry-chain',
      body: any
    if (request.method === 'GET' && url.pathname === dataSourcePaths[0] && !url.search) {
    } else if (request.method === 'POST' && url.pathname === dataSourcePaths[1] && !url.search) {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
        return reply({ error: '需要 JSON 请求' }, 400)
      const raw = await request.text()
      if (raw.length > 10000) return reply({ error: '请求过大' }, 400)
      try {
        body = JSON.parse(raw)
      } catch {
        return reply({ error: '请求格式无效' }, 400)
      }
      if (
        !body ||
        Array.isArray(body) ||
        !['prepare', 'commit', 'query'].includes(body.operation) ||
        'session_id' in body
      )
        return reply({ error: '操作无效' }, 400)
      const { operation, ...payload } = body
      if (
        operation === 'prepare' &&
        !['bootstrap', 'refresh', 'refresh_universe', 'delete'].includes(payload.action)
      )
        return reply({ error: '页面不能提交研报增量' }, 400)
      path += '/' + operation
      body = operation === 'query' ? payload : { ...payload, session_id: 'ui-data-sources-owner' }
    } else return reply({ error: '请求不支持' }, 405)
    try {
      const r = await fetch(new URL(path, base), {
        method: body ? 'POST' : 'GET',
        redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(body ? 300000 : 15000)]),
      })
      return reply(await r.json(), r.status)
    } catch {
      return reply(
        {
          error: body
            ? '连接中断，请先刷新资料源状态核对，不要重复提交。'
            : '资料源状态读取失败，请重试。',
        },
        503,
      )
    }
  }
}
