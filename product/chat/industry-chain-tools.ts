import { businessTool, requestKey, confirmBusiness, cancelled, type Ask } from './business-tools.js'
export const industryChainToolNames = ['manage_industry_chain']
const text = { type: 'string', minLength: 1, maxLength: 1000 }
const code = { type: 'string', pattern: '^(?:[0-9]{6}|[0-9]{8})$' }
const refs = { type: 'array', minItems: 1, maxItems: 20, uniqueItems: true, items: text }
const object = (properties: Record<string, unknown>, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false })
const list = (items: unknown, maxItems = 30) => ({ type: 'array', maxItems, items })
const locations = list(object({evidence_id:text,page:{type:'integer',minimum:1,maximum:400},quote:{type:'string',minLength:1,maxLength:240}}),20)
const relation = object({ id: text, name: text, type: { type: 'string', enum: ['direct','inferred'] }, share: { type: ['number','null'], minimum: 0, maximum: 100 }, confidence: { type: ['number','null'], minimum: 0, maximum: 1 }, note: text })
const company = object({ code, source_evidence_ids: refs, source_locations:locations,
  materials: list(object({ name: text, suppliers: list(relation) })), products: list(object({ name: text, customers: list(relation) })),
  related: list(object({ name: text, relation: text, note: text, code }, ['name','relation','note'])),
  metrics: list(object({ name: text, value: text, unit: text, period: text, note: text }), 50) })
const link = object({ source: code, target: code, kind: { type: 'string', enum: ['supplier','customer'] }, item: text, confidence: { type: 'number', minimum: 0, maximum: 1 }, note: text, source_evidence_ids: refs, source_locations:locations })
export function createIndustryChainTools(address: string, token: string, ask?: Ask) {
  const base = new URL(address)
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.pathname !== '/' || base.username || base.password || base.search || base.hash || !token) throw Error('产业链 API 无效')
  return [businessTool('manage_industry_chain', '读取当前实例产业链资料状态；经原生确认下载、刷新、删除资料或保存研报提取的产业链增量。overlay 中每项须引用本会话 research_report_document_lookup 正文证据编号和 source_locations（evidence_id/page/quote）。报价、标题、评级不能作关系正文证据，明确披露/推断及未知比例；程序校验并保存，模型不能直接写库。bootstrap/refresh 需用户确认第三方使用条件。资料查询使用现有产业链研究工具。', {
    action: { type: 'string', enum: ['status','bootstrap','refresh','delete','refresh_universe','overlay','clear_overlay'] },
    companies: list(company, 20), inferred_links: list(link, 100), codes: list(code, 100),
  }, ['action'], async (args, exec) => {
    const session = exec.agent!.session.id, key = requestKey(exec, 'industry-chain')
    const request = async (path: string, body?: unknown) => {
      const r = await fetch(new URL('/industry-chain' + path, base), { method: body ? 'POST' : 'GET', redirect: 'error', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.any([exec.signal, AbortSignal.timeout(path === '/commit' ? 300000 : 20000)]) })
      const data = await r.json(); if (!r.ok) throw Error(data.detail || '产业链操作失败'); return data
    }
    if (args.action === 'status') return request('')
    const payload = args.action === 'overlay' ? { companies: args.companies, inferred_links: args.inferred_links } : args.action === 'clear_overlay' ? { codes: args.codes } : ['bootstrap','refresh'].includes(args.action) ? { acknowledge_source_terms: true } : {}
    const preview = await request('/prepare', { session_id: session, request_key: key, action: args.action, payload })
    if (!await confirmBusiness(ask, exec, preview.summary) || exec.signal.aborted) return cancelled
    try { return await request('/commit', { session_id: session, request_key: key, preview_id: preview.preview_id }) }
    catch { return { status: 'unconfirmed', guidance: '本次提交结果未知，请先查询资料源状态，不要自动重复提交。', preview_id: preview.preview_id } }
  }, true)]
}
