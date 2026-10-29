/** 认证围栏由 DSH Connection 拥有；仅转发有界成果字节，拒绝任意路径。 */
export const deliverableDownloadPath = '/api/huohuo/deliverables/download'
type DeliveryReader = (
  sessionId: string,
  seq: number,
  index: number,
  signal: AbortSignal,
) => Promise<string | undefined>
export function createDeliverableDownload(
  address: string,
  token: string,
  readDelivery: DeliveryReader,
) {
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
    throw Error('成果 API 配置无效')
  return async (request: Request) => {
    const fail = (status: number, detail: string) =>
      Response.json({ detail }, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    if (request.method !== 'GET' || url.pathname !== deliverableDownloadPath)
      return fail(405, '请求不支持')
    const query = url.searchParams
    if (
      [...query.keys()].some(
        (k) =>
          !['id', 'part', 'sessionId', 'seq', 'index'].includes(k) || query.getAll(k).length !== 1,
      )
    )
      return fail(400, '下载参数无效')
    let id = query.get('id'),
      part = query.get('part') ?? 'file'
    let session: string | undefined
    try {
      if (query.has('sessionId')) {
        if (id || query.has('part')) return fail(400, '下载坐标不能混用')
        session = query.get('sessionId')!
        const seq = query.get('seq') ?? '',
          index = query.get('index') ?? ''
        if (
          !session ||
          session.length > 200 ||
          !/^\d+$/.test(seq) ||
          !/^\d+$/.test(index) ||
          !Number.isSafeInteger(Number(seq)) ||
          Number(index) > 1
        )
          return fail(400, '下载坐标无效')
        const path = await readDelivery(session, Number(seq), Number(index), request.signal)
        const match = path?.match(/[/\\]\.huohuo-deliverables[/\\]([0-9a-f]{64})[/\\]([^/\\]+)$/)
        if (!match) return fail(404, '这条交付记录没有可下载的研究成果')
        id = match[1]
        part = match[2] === '交付说明.json' ? 'metadata' : 'file'
      } else if (query.has('seq') || query.has('index')) return fail(400, '缺少会话坐标')
      if (!id || !/^[0-9a-f]{64}$/.test(id) || !['file', 'metadata'].includes(part))
        return fail(400, '成果编号或格式无效')
      const response = await fetch(new URL('/deliverables/download', base), {
        method: 'POST',
        redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, part, ...(session ? { session_id: session } : {}) }),
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(30000)]),
      })
      if (!response.ok)
        return fail(
          response.status === 403 ? 403 : 404,
          '成果不存在、不可读取或已改变；请核对原记录',
        )
      const size = Number(response.headers.get('Content-Length'))
      if (!Number.isSafeInteger(size) || size < 1 || size > 10 * 1024 * 1024)
        return fail(502, '成果大小超出限制')
      const bytes = await response.arrayBuffer()
      if (bytes.byteLength !== size) return fail(502, '文件传输未完成，请重试下载原成果')
      const headers = new Headers({
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      })
      for (const name of ['Content-Type', 'Content-Disposition', 'X-Content-SHA256']) {
        const value = response.headers.get(name)
        if (value) headers.set(name, value)
      }
      return new Response(bytes, { headers })
    } catch {
      return fail(503, '下载未完成，请重试原成果；不会重新执行研究')
    }
  }
}
