import { createHash } from 'node:crypto'
import type { ToolDefinition, ToolRunContext } from '@deepseek-ai/dsh-tools'
export const transferToolNames = ['read_legacy_imports', 'import_legacy_data']
export type TransferQuestion = (questions: unknown[], exec: ToolRunContext) => Promise<any>
const text = { type: 'string', minLength: 1, maxLength: 200 }
const categories = ['holdings', 'watchlist', 'strategies', 'research', 'mandates']
const names: Record<string, string> = {
  holdings: '持仓与历史成交',
  watchlist: '自选',
  strategies: '策略候选',
  research: '旧研究与对话档案',
  mandates: '暂停委托',
  archives: '只读档案',
}
export function transferConfirmed(answer: any): boolean {
  return (
    !answer?.pending && !answer?.cancelled &&
    Array.isArray(answer?.answers) &&
    answer.answers.length === 1 &&
    answer.answers[0].id === 'transfer-confirm' &&
    !answer.answers[0].custom &&
    Array.isArray(answer.answers[0].selected) &&
    answer.answers[0].selected.length === 1 &&
    answer.answers[0].selected[0] === '确认导入'
  )
}
export function createTransferTools(
  address: string,
  token: string,
  ask?: TransferQuestion,
): ToolDefinition[] {
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
    throw Error('导入 API 配置无效')
  return transferToolNames.map((name) => {
    const read = name === 'read_legacy_imports'
    return {
      name,
      description: read
        ? '查询当前用户在设置中已上传的旧产品文件、当前会话导入预览/回执和只读旧资料。operation=uploads/status/changes/archive。旧资料不能作为 DSH 会话或新研究证据；查询不执行导入。'
        : '迁入设置中已上传的旧产品 JSON 数据。只接受 upload_id 与分类，不接受本地路径、URL、文件正文、凭据或确认回答。程序生成逐项预览并等待原生用户确认，再以单事务导入；策略重新待验证、委托暂停、历史成交不重算持仓。冲突默认保留当前，使用导入值须明确选择 use_import。',
      parameters: read
        ? {
            type: 'object',
            properties: {
              operation: { type: 'string', enum: ['uploads', 'status', 'changes', 'archive'] },
              preview_id: text,
              archive_id: text,
              category: { type: 'string', enum: categories },
              offset: { type: 'integer', minimum: 0, maximum: 50000 },
              limit: { type: 'integer', minimum: 1, maximum: 100 },
            },
            required: ['operation'],
            additionalProperties: false,
          }
        : {
            type: 'object',
            properties: {
              upload_id: text,
              selected: {
                type: 'array',
                items: { type: 'string', enum: categories },
                minItems: 1,
                maxItems: 5,
                uniqueItems: true,
              },
              rules: {
                type: 'object',
                properties: Object.fromEntries(
                  categories.map((x) => [
                    x,
                    { type: 'string', enum: ['keep_local', 'use_import'] },
                  ]),
                ),
                additionalProperties: false,
              },
            },
            required: ['upload_id', 'selected'],
            additionalProperties: false,
          },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_a: any, v: any) => [{ type: 'text', text: JSON.stringify(v) }],
      },
      timeoutMs: 2147483000,
      async execute(input: any, exec: ToolRunContext) {
        const session = exec.agent?.session.id
        if (!session || !exec.callId || !input || typeof input !== 'object' || Array.isArray(input))
          throw Error('缺少可信会话或参数无效')
        const fields = read
          ? ['operation', 'preview_id', 'archive_id', 'category', 'offset', 'limit']
          : ['upload_id', 'selected', 'rules']
        if (Object.keys(input).some((k) => !fields.includes(k)))
          throw Error('不支持文件路径、确认回答或其他额外参数')
        const key =
          'transfer:' +
          createHash('sha256')
            .update(JSON.stringify([session, exec.callId]))
            .digest('hex')
        let previewId: string | undefined
        async function request(operation: string, payload: any) {
          const response = await fetch(new URL('/transfer/' + operation, base), {
            method: 'POST',
            redirect: 'error',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, session_id: session }),
            signal: AbortSignal.any([exec.signal, AbortSignal.timeout(30000)]),
          })
          const result = (await response.json()) as any
          if (!response.ok) throw Error(result.detail || '导入操作未完成，请查询同一预览的回执')
          return result
        }
        try {
          if (read) {
            const allowed: Record<string, string[]> = {
              uploads: ['operation'],
              status: ['operation', 'preview_id'],
              changes: ['operation', 'preview_id', 'category', 'offset', 'limit'],
              archive: ['operation', 'archive_id', 'category', 'offset', 'limit'],
            }
            if (
              !allowed[input.operation] ||
              Object.keys(input).some((k) => !allowed[input.operation].includes(k))
            )
              throw Error('查询字段与操作不匹配')
            const { operation, ...payload } = input
            return await request(operation, payload)
          }
          if (!ask) throw Error('原生用户确认尚未装配，未提交导入')
          const preview = await request('prepare', {
            upload_id: input.upload_id,
            selected: input.selected,
            rules: input.rules ?? {},
            request_key: key,
          })
          previewId = preview.preview_id
          if (!preview.can_commit) return preview
          const summary = Object.entries(preview.summary)
            .map(
              ([id, value]: [string, any]) =>
                `${names[id] ?? id}：${value.incoming ?? 0} 项${typeof value.conflicts === 'number' && value.conflicts ? `，冲突 ${value.conflicts} 项（${preview.rules[id] === 'use_import' ? '使用导入值' : '保留当前值'}）` : ''}`,
            )
            .join('\n')
          const details = (preview.changes?.items ?? [])
            .map(
              (x: any) =>
                `${x.name}${x.code ? `（${x.code}）` : ''} · ${x.kind}\n原值：${JSON.stringify(x.before)}\n新值：${JSON.stringify(x.after)}`,
            )
            .join('\n')
          const answer = await ask(
            [
              {
                id: 'transfer-confirm',
                header: '确认旧数据迁入',
                question: `${summary}\n\n${details}\n${preview.changes.total > 20 ? `另有 ${preview.changes.total - 20} 项，可取消后用 read_legacy_imports changes 分页核对。` : ''}\n${preview.warnings.join('\n')}\n确认将一次导入所选全部分类；不会恢复旧任务或通知授权。`,
                options: [
                  { label: '确认导入', description: '按当前预览写入正式记录与只读档案。' },
                  { label: '暂不导入', description: '不修改正式数据，保留上传文件供重新核对。' },
                ],
              },
            ],
            exec,
          )
          if (!transferConfirmed(answer) || exec.signal.aborted) {
            if (!exec.signal.aborted) await request('cancel', { preview_id: previewId })
            return {
              status: 'cancelled',
              preview_id: previewId,
              guidance: '未获得原生用户确认，未提交导入。',
            }
          }
          return await request('commit', { preview_id: previewId, request_key: key })
        } catch (e) {
          return {
            status: 'unconfirmed',
            preview_id: previewId,
            request_key: key,
            error: e instanceof Error ? e.message : '连接中断',
            guidance:
              '若已有 preview_id，先用 read_legacy_imports status 核对回执。不要自动更换请求标识重复提交；文件请从设置中的旧数据导入上传。',
          }
        }
      },
    } as ToolDefinition
  })
}
