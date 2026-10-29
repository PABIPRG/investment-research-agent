/** 只生成受控成果，不允许模型指定本机路径或代码。 */
import type { ToolRunContext } from '@deepseek-ai/dsh-tools'
import { businessApi, businessTool } from './business-tools.js'

export const deliverableToolNames = ['create_research_file', 'read_research_file']
export interface ResearchFile {
  id: string; filename: string; file_path: string; metadata_path: string; bytes: number
  content_kind: string; download_url: string; metadata_url: string
}
const text = { type: 'string', minLength: 1, maxLength: 100 }
const scalar = { anyOf: [{ type: 'string', maxLength: 16000 }, { type: 'number' }, { type: 'null' }] }
export function createDeliverableTools(address: string, token: string, created?: (exec: ToolRunContext, file: ResearchFile) => void) {
  const api = businessApi(address, token)
  const properties = {
    format: { type: 'string', enum: ['csv', 'json', 'xlsx'] },
    title: { type: 'string', minLength: 1, maxLength: 60 },
    content_kind: { type: 'string', enum: ['evidence', 'model_analysis'] },
    evidence_ids: { type: 'array', maxItems: 8, uniqueItems: true, items: { type: 'string', minLength: 1, maxLength: 200 } },
    limitations: { type: 'string', maxLength: 4000 },
    tables: { type: 'array', maxItems: 6, items: {
      type: 'object', additionalProperties: false, required: ['name', 'columns'], properties: {
        name: { type: 'string', minLength: 1, maxLength: 31 },
        evidence_id: { type: 'string', minLength: 1, maxLength: 200 },
        records_path: { type: 'array', maxItems: 8, items: text },
        columns: { type: 'array', minItems: 1, maxItems: 40, items: {
          type: 'object', additionalProperties: false, required: ['key', 'label', 'type'], properties: {
            key: text, label: text, type: { type: 'string', enum: ['text', 'number', 'percent', 'date'] },
            unit: { type: 'string', minLength: 1, maxLength: 50 },
          },
        } },
        rows: { type: 'array', maxItems: 5000, items: { type: 'object', additionalProperties: scalar } },
      },
    } },
  }
  return [
    businessTool('create_research_file', '按用户请求生成 CSV、JSON 或基础 Excel 并交付下载。原始数据使用 evidence 模式，引用本会话 evidence_ids；表格用 evidence_id 和 records_path 指向真实记录数组，不填写 rows。模型整理使用 model_analysis 和 rows，明确来源/限制，不冒充原始事实。证券代码用 text；percent 使用小数。CSV 只支持单表并对前导零/公式文本增加单引号，需无损数据请选择 JSON/XLSX。单次最多六表、五万单元格、10 MiB。不执行公式、不指定文件路径、不发通知。',
      properties, ['format', 'title', 'content_kind', 'evidence_ids', 'limitations'], async (args, exec) => {
        let file: ResearchFile
        try { file = await api('/deliverables/create', exec, { session_id: exec.agent!.session.id, call_id: exec.callId, spec: args }) as ResearchFile }
        catch (error: any) {
          if (error.code !== 'submission_unknown' && !(error.http_status >= 500)) throw error
          return { ok: false, error: 'submission_unknown', source_call_id: exec.callId, guidance: '生成结果未知。使用 read_research_file 的 source_call_id 核对本次调用，不要重复生成。' }
        }
        created?.(exec, file)
        return { ok: true, file, guidance: '已生成独立文件及交付说明，使用文件卡片下载。只在 saved/ok 回执后说明完成；旧文件为生成时快照。' }
      }),
    businessTool('read_research_file', '核对本会话已生成成果及下载入口。重复生成结果未知时以原调用的成果编号核对；读取不重新研究、不更改文件。',
      { id: { type: 'string', pattern: '^[0-9a-f]{64}$' }, source_call_id: { type: 'string', minLength: 1, maxLength: 200 } }, [], async (args, exec) => {
        if (Boolean(args.id) === Boolean(args.source_call_id)) throw Error('提供成果编号或原生成调用编号之一')
        const file = await api('/deliverables/inspect', exec, { session_id: exec.agent!.session.id, ...args }) as ResearchFile
        created?.(exec, file)
        return { ok: true, file }
      }),
  ]
}
