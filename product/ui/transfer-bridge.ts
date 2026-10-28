/** 固定上传/预览/确认桥；不接收页面自行声明的身份、会话、文件路径或服务地址。 */
export const transferPath = '/api/huohuo/transfer'
export function createTransferBridge(address: string, token: string) {
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
    throw Error('导入 API 配置无效')
  return async (request: Request) => {
    const reply = (value: unknown, status = 200) =>
      Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } })
    const url = new URL(request.url)
    if (request.method !== 'POST' || url.pathname !== transferPath || url.search)
      return reply({ detail: '请求不支持' }, 405)
    if (request.headers.get('Content-Type')?.split(';')[0] !== 'application/json')
      return reply({ detail: '需要 JSON 请求' }, 400)
    const raw = await request.text()
    if (Buffer.byteLength(raw) > 42 * 1024 * 1024)
      return reply({ detail: '上传请求超过大小限制' }, 400)
    let body: any
    try {
      body = JSON.parse(raw)
    } catch {
      return reply({ detail: '请求格式无效' }, 400)
    }
    if (
      !body ||
      typeof body !== 'object' ||
      Array.isArray(body) ||
      'session_id' in body ||
      'principal' in body ||
      ![
        'uploads',
        'upload',
        'prepare',
        'commit',
        'status',
        'changes',
        'cancel',
        'remove_upload',
        'archive',
      ].includes(body.operation)
    )
      return reply({ detail: '导入操作无效' }, 400)
    const { operation, ...payload } = body
    if (operation !== 'upload' && Buffer.byteLength(raw) > 100_000)
      return reply({ detail: '请求超过大小限制' }, 400)
    try {
      const response = await fetch(new URL('/transfer/' + operation, base), {
        method: 'POST',
        redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, session_id: 'ui-transfer-owner' }),
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(60000)]),
      })
      return reply(await response.json(), response.status)
    } catch {
      return reply(
        {
          detail:
            operation === 'commit'
              ? '提交结果暂不确定，请检查同一预览回执，不要重复导入。'
              : '请求未完成，请重试读取状态。',
        },
        503,
      )
    }
  }
}
