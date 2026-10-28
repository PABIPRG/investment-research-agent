/** Reuses the existing user-scoped directory; never accepts a destination or credential. */
export const securityPath = '/api/huohuo/security-search'
export function createSecurityBridge(address: string, token: string) {
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
    throw Error('证券 API 配置无效')
  return async (request: Request): Promise<Response> => {
    const reply = (status: number, data: unknown) =>
      Response.json(data, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    if (request.method !== 'POST' || url.pathname !== securityPath || url.search)
      return reply(405, { detail: '不支持的搜索请求' })
    if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
      return reply(400, { detail: '需要 JSON 请求' })
    const raw = await request.text()
    if (raw.length > 2000) return reply(400, { detail: '搜索词过长' })
    let input: unknown
    try {
      input = JSON.parse(raw)
    } catch {
      return reply(400, { detail: '请求格式无效' })
    }
    if (
      !input ||
      typeof input !== 'object' ||
      Array.isArray(input) ||
      Object.keys(input).join() !== 'query' ||
      !('query' in input) ||
      typeof input.query !== 'string' ||
      !input.query.trim() ||
      input.query.length > 100
    )
      return reply(400, { detail: '请输入名称或代码' })
    try {
      const r = await fetch(new URL('/entities/search', base), {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input.query.trim() }),
        redirect: 'error',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(15000)]),
      })
      return reply(r.status, await r.json())
    } catch {
      return reply(503, { detail: '证券资料暂时无法读取，请重试；这不代表证券不存在。' })
    }
  }
}
