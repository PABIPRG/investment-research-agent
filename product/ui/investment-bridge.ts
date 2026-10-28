/** 固定投资事实接口；主体和凭据由已认证的 DSH Host 注入。 */
export const investmentPaths = ['/api/huohuo/investment', '/api/huohuo/investment-command']
export function createInvestmentBridge(address: string, token: string) {
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
    throw new Error('投资 API 配置无效')
  return async (request: Request): Promise<Response> => {
    const reply = (status: number, value: unknown) =>
      Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    let path = '/investment'
    let method = 'GET'
    let body: unknown
    if (request.method === 'GET' && url.pathname === investmentPaths[0] && !url.search) {
      /* read */
    } else if (request.method === 'POST' && url.pathname === investmentPaths[1] && !url.search) {
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
        return reply(400, { detail: '需要 JSON 请求' })
      const raw = await request.text()
      if (raw.length > 20000) return reply(400, { detail: '请求过大' })
      let input: any
      try {
        input = JSON.parse(raw)
      } catch {
        return reply(400, { detail: '请求格式无效' })
      }
      if (
        !input ||
        typeof input !== 'object' ||
        Array.isArray(input) ||
        ![
          'preview',
          'commit',
          'snapshot',
          'collection',
          'bind-collection',
          'inspect-preview',
        ].includes(input.action)
      )
        return reply(400, { detail: '不支持的投资操作' })
      const { action, ...payload } = input
      if (action === 'inspect-preview') {
        if (
          Object.keys(payload).length !== 1 ||
          typeof payload.preview_id !== 'string' ||
          !/^[0-9a-f-]{36}$/.test(payload.preview_id)
        )
          return reply(400, { detail: '预览标识无效' })
        path += '/previews/' + payload.preview_id
      } else {
        path += '/' + action
        body = payload
        method = 'POST'
      }
    } else return reply(405, { detail: '不支持的请求' })
    try {
      const response = await fetch(new URL(path, base), {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        redirect: 'error',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
      })
      const raw = await response.text()
      if (raw.length > 8_000_000) return reply(502, { detail: '响应过大，请缩小查询范围' })
      return reply(response.status, JSON.parse(raw))
    } catch {
      return reply(503, {
        detail: body
          ? '连接中断，保存结果待核对。请刷新；重试会复用原请求标识。'
          : '事实读取失败，请重试；这不代表空仓。',
      })
    }
  }
}
