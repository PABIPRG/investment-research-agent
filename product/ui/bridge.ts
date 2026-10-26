/** Read-only browser bridge. DSH authenticates the owner before invoking it. */
const routes: Record<string, string | null> = {
  '/api/huohuo/executions': null, '/api/huohuo/execution': '',
  '/api/huohuo/events': '/events', '/api/huohuo/evidence': '/evidence',
}
export const queryPaths = Object.keys(routes)
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function reply(status: number, data: unknown): Response {
  return Response.json(data, { status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } })
}

/** Bind the user capability to the Host, never to browser-supplied input. */
export function createQueryBridge(address: string, token: string): (request: Request) => Promise<Response> {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/'
      || base.username || base.password || base.search || base.hash || !token) throw new Error('查询 API 配置无效')
  return async request => {
    if (request.method !== 'GET') return reply(405, { error: 'read_only' })
    const url = new URL(request.url)
    if (!Object.hasOwn(routes, url.pathname)) return reply(404, { error: 'not_found' })
    const suffix = routes[url.pathname]
    const id = url.searchParams.get('id')
    if (suffix === null ? url.search !== '' : !id || !uuid.test(id) || [...url.searchParams].length !== 1) {
      return reply(400, { error: 'invalid_query' })
    }
    const path = suffix === null ? '/executions' : `/executions/${id}${suffix}`
    // List includes up to 50 complete results, each bounded by the backend at 100KB.
    const maxBytes = suffix === null || suffix === '/evidence' || suffix === '/events' ? 8_000_000 : 2_000_000
    const controller = new AbortController()
    const signal = AbortSignal.any([request.signal, controller.signal, AbortSignal.timeout(8000)])
    try {
      const response = await fetch(new URL(path, base), { method: 'GET', redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' }, signal })
      if (!response.ok) {
        await response.body?.cancel()
        return reply(response.status === 404 ? 404 : response.status === 403 ? 403 : 503,
          { error: response.status === 404 ? 'not_found' : response.status === 403 ? 'forbidden' : 'backend_unavailable' })
      }
      const reader = response.body?.getReader()
      if (!reader) return reply(502, { error: 'invalid_response' })
      const chunks: Uint8Array[] = []; let size = 0
      try {
        while (true) {
          const chunk = await reader.read(); if (chunk.done) break
          size += chunk.value.byteLength
          if (size > maxBytes) { await reader.cancel(); return reply(502, { error: 'response_too_large' }) }
          chunks.push(chunk.value)
        }
      } finally { reader.releaseLock() }
      try { return reply(200, JSON.parse(Buffer.concat(chunks).toString('utf8'))) }
      catch { return reply(502, { error: 'invalid_response' }) }
    } catch { return reply(503, { error: 'backend_unavailable' }) }
    finally { controller.abort() }
  }
}
