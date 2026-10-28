import { businessTool } from './business-tools.js'
export const marketToolNames = ['query_market']
export function createMarketTools(address: string, token: string) {
  return [businessTool('query_market', '读取真实市场资料：行情/技术指标需已确认对象，news 可查询该对象新闻或全市场快讯，scan 查询市场榜单，brief 整理盘前/盘后资料包。保留来源时间、陈旧与缺失字段。只读查询不会建立监控或授权通知；持续跟进通过 create_mandate 确认范围和联系规则。', {
    operation: { type: 'string', enum: ['quotes', 'technical', 'news', 'brief', 'scan'] },
    confirmation_id: { type: 'string', description: 'quotes/technical/brief 必填本会话有效实体确认。news 省略时是全市场快讯。' },
    kind: { type: 'string', enum: ['gainers', 'volume_ratio', 'limit', 'turnover', 'amount'] },
    limit: { type: 'integer', minimum: 1, maximum: 50 },
    lookback: { type: 'integer', minimum: 30, maximum: 250 },
    period: { type: 'string', enum: ['pre', 'post'] },
    include_slow: { type: 'boolean', description: '仅 news/brief 可选，默认 false。true 加入扩展全市场新闻源，可能较慢或部分不可用；定向证券 news 不允许开启。' },
    min_amount_yi: { type: 'number', minimum: 0 },
  }, ['operation'], async (args, exec) => {
    const response = await fetch(new URL('/market/query', address), {
      method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: exec.agent!.session.id, call_id: exec.callId, arguments: args }),
      signal: AbortSignal.any([exec.signal, AbortSignal.timeout(45000)]),
    })
    const data = await response.json()
    return { ok: response.ok, http_status: response.status, data }
  }, true)]
}
