/** Authenticated DSH transport; fixed commands, never arbitrary backend paths. */
export const mandatePaths = ['/api/huohuo/mandates', '/api/huohuo/mandate', '/api/huohuo/mandate-command']
export function createMandateBridge(address: string, token: string) {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/' || base.username || base.password || base.search || base.hash || !token) throw new Error('委托 API 配置无效')
  return async (request: Request): Promise<Response> => {
    const reply = (status: number, value: unknown) => Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url); let path = '/mandates'; let body: any
    if (request.method === 'GET' && url.pathname === mandatePaths[0] && !url.search) { /* list */ }
    else if (request.method === 'GET' && url.pathname === mandatePaths[1] && [...url.searchParams].length === 1 && /^MND_[a-f0-9]{32}$/.test(url.searchParams.get('id') ?? '')) path += '/' + url.searchParams.get('id')
    else if (request.method === 'POST' && url.pathname === mandatePaths[2] && !url.search) {
      // The owner-authenticated connection service invokes this bridge; no credential in browser.
      if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json') return reply(400, { detail: '需要 JSON 请求' })
      const raw = await request.text(); if (raw.length > 20000) return reply(400, { detail: '请求过大' })
      let input: any; try { input = JSON.parse(raw) } catch { return reply(400, { detail: '请求格式无效' }) }
      if (!input || typeof input !== 'object' || Array.isArray(input) || !['create','pause','resume','end','revise'].includes(input.action)) return reply(400, { detail: '不支持的操作' })
      const { action, mandate_id, ...payload } = input
      if (action !== 'create') {
        if (!/^MND_[a-f0-9]{32}$/.test(mandate_id)) return reply(400, { detail: '委托标识无效' })
        path += `/${mandate_id}/${action}`
      } else if (mandate_id !== undefined) return reply(400, { detail: '创建不接受已有标识' })
      body = payload
    } else return reply(405, { detail: '不支持的请求' })
    try {
      const response = await fetch(new URL(path, base), { method: body ? 'POST' : 'GET', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]) })
      const raw = await response.text(); if (raw.length > 8_000_000) return reply(502, { detail: '响应过大，请缩小查询范围' })
      return reply(response.status, JSON.parse(raw))
    } catch { return reply(503, { detail: body ? '连接中断，操作可能已保存。请刷新核对，重试将复用相同请求标识。' : '后台暂时不可用，请稍后刷新。' }) }
  }
}
