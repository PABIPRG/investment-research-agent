/** Read-only projection of the same definitions installed by the product preset. */
import { readFile, readdir } from 'node:fs/promises'
import { allowedChatToolNames, createChatTools, nativeChatToolNames } from '../../chat/tools.js'
import { createEntityConfirmationTool } from '../../chat/entity-tools.js'
import { chatSkillNames } from '../../chat/policy.js'
import { researchToolCatalog } from '../../tools/research-tools.generated.js'
import type { Capability, CapabilityCatalog } from './model.js'

const toolTitles: Record<string, string> = {
  read_legacy_imports: '查看旧数据与导入回执',
  import_legacy_data: '导入已上传的旧数据',
  manage_industry_chain: '管理产业链资料与研报增量',
  query_market: '查询行情、新闻与市场扫描',
  read_strategy_records: '读取策略与验证记录',
  manage_strategy: '建立与验证策略',
  submit_quote_research: '提交单次报价研究',
  list_research: '查询单次研究记录',
  get_research: '查看单次研究详情',
  research_events: '查看研究进展',
  research_evidence: '查看研究证据',
  cancel_research: '取消单次研究',
  retry_research: '重试单次研究',
  resolve_research_scope: '识别研究对象',
  search_securities: '搜索证券',
  create_mandate: '创建持续委托',
  list_mandates: '查询我的委托',
  get_mandate: '查看委托详情',
  manage_mandate: '调整与管理委托',
  read_investment_facts: '读取投资记录',
  preview_investment_change: '预览投资记录变更',
  commit_investment_change: '确认保存投资记录',
  read_investment_collection: '读取持仓与自选集合',
  bind_mandate_investment_collection: '关联委托与投资记录',
  read_notification_settings: '读取提醒配置',
  list_notification_deliveries: '查询联系记录',
  update_notification_preferences: '修改提醒偏好',
  clear_notification_channel: '清除提醒渠道',
  open_product_view: '打开产品页面',
  confirm_research_entities: '确认研究对象',
}
const nativeTools = [
  {
    name: 'skill',
    title: '加载 Skill',
    description: '按需加载产品自带的研究与记录方法。加载方法不会增加工具权限。',
  },
  {
    name: 'ask_user_question',
    title: '向用户提问',
    description: '通过原生问题面板澄清信息或让用户选择，回答不等于任意业务授权。',
  },
]
const registeredNote =
  '本版本已注册并列入火火允许名单。资料源和执行结果以实际调用回执为准；本页不探测外部服务。'

export async function readCapabilityCatalog(
  address: string,
  token: string,
): Promise<CapabilityCatalog> {
  const tools = [
    ...createChatTools(address, token),
    createEntityConfirmationTool(address, token, async () => {
      throw Error('能力目录不能执行确认')
    }),
  ]
  const research = new Map<string, (typeof researchToolCatalog)[number]>(
    researchToolCatalog.map((x) => [x.name, x]),
  )
  const items: Capability[] = tools
    .filter((x) => allowedChatToolNames.includes(x.name))
    .map((tool) => {
      const spec = research.get(tool.name)
      const status = spec?.requires_authorization
        ? 'restricted'
        : spec && spec.availability !== 'configured'
          ? 'unconnected'
          : 'registered'
      return {
        id: tool.name,
        title: spec?.title ?? toolTitles[tool.name] ?? tool.name,
        kind: 'tool',
        description: tool.description,
        category: spec?.category ?? '产品业务',
        source: spec ? '火火研究工具' : '火火业务工具',
        status,
        note:
          status === 'restricted'
            ? '当前独立实例尚未接通此项授权流程，调用不会执行。这里没有可用的授权开关。'
            : status === 'unconnected'
              ? '当前独立实例未接入该能力所需的服务或可靠来源；不代表已可用。'
              : registeredNote,
        ...([
          'read_strategy_records',
          'manage_strategy',
          'strategy_pool_lookup',
          'strategy_evolution_preview',
          'strategy_attribution_lookup',
        ].includes(tool.name)
          ? { action: 'strategy' as const }
          : {}),
        ...(tool.name.includes('investment') ? { action: 'investment' as const } : {}),
      }
    })
  for (const tool of nativeTools.filter((x) => nativeChatToolNames.includes(x.name))) {
    items.push({
      id: tool.name,
      title: tool.title,
      kind: 'tool',
      description: tool.description,
      category: '交互基础',
      source: 'DSH 原生装配',
      status: 'registered',
      note: '产品 Bundle 声明装载的原生基础工具，仍受火火允许名单约束。',
    })
  }
  if (allowedChatToolNames.some((name) => !items.some((x) => x.id === name)))
    throw Error('工具目录与装配不一致')
  const root = new URL('../../../../product/skills/chat/', import.meta.url)
  for (const directory of await readdir(root, { withFileTypes: true })) {
    if (!directory.isDirectory()) continue
    const text = await readFile(new URL(`${directory.name}/SKILL.md`, root), 'utf8')
    const front = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)?.[1] ?? ''
    const id = /^name:\s*(.+)$/m.exec(front)?.[1]?.trim()
    if (!id || !chatSkillNames.includes(id)) continue
    const description = /^description:\s*(.+)$/m.exec(front)?.[1]?.trim()
    const title = /^#\s+(.+)$/m.exec(text)?.[1]?.trim()
    if (!description || !title) throw Error('自带 Skill 目录无效')
    items.push({
      id,
      title,
      description,
      kind: 'skill',
      category: '任务方法',
      source: '火火自带 Skill',
      status: 'registered',
      note: '来自当前安装包的 Skill 文件，并已列入产品允许名单。Skill 负责方法说明，不授予额外权限。',
      ...(id === 'huohuo-strategies' ? { action: 'strategy' as const } : {}),
      ...(id === 'huohuo-investment-facts' ? { action: 'investment' as const } : {}),
    })
  }
  if (chatSkillNames.some((id) => !items.some((x) => x.kind === 'skill' && x.id === id)))
    throw Error('Skill 目录与允许名单不一致')
  items.sort((a, b) => a.kind.localeCompare(b.kind) || a.title.localeCompare(b.title, 'zh-CN'))
  return { items, read_at: new Date().toISOString(), scope: 'product-preset' }
}
