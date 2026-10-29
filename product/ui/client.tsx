import { TransferSection } from './transfer/TransferSection.js'
import { DataSourcesSection } from './data-sources/DataSourcesSection.js'
import { installProductNavigation } from './navigation.js'
import { CapabilitiesSection } from './capabilities/CapabilitiesSection.js'
import { StrategyPage } from './strategies/StrategyPage.js'
import { ActivityPage, PlannedPage } from './Activity.js'
import type { DshUiContext } from './dsh-face.js'
import { InvestmentPage } from './Investment.js'
import { NotificationsPage } from './Notifications.js'
import { ResearchPage } from './research/ResearchPage.js'
import { installShell } from './Shell.js'
import { BrandMark, BrandName, QueryIcon, brandMetadata } from './shell/Brand.js'
import { DownloadAction } from './deliverables/DownloadAction.js'
declare const __HUOHUO_CSS__: string
const panelId = 'huohuo-research'
export const inject = ['slots', 'layout', 'uiWorkspace', 'sessions', 'inputTriggers', 'connection']
export function apply(ctx: DshUiContext): void {
  try {
    ctx.slots.inject('deliverables.file.actions', () =>
      ctx.slots.register(
        { name: 'deliverables.file.actions', id: 'huohuo-download', order: 1 },
        DownloadAction,
      ),
    )
    installShell(ctx)
    installProductNavigation(ctx)
    ctx.slots.inject('settings.section', () =>
      ctx.slots.register(
        { name: 'settings.section', id: 'huohuo-transfer', order: 14, label: '旧数据导入' },
        TransferSection as any,
      ),
    )
    ctx.slots.inject('settings.section', () =>
      ctx.slots.register(
        { name: 'settings.section', id: 'huohuo-data-sources', order: 13, label: '资料源' },
        DataSourcesSection as any,
      ),
    )
    ctx.slots.inject('settings.section', () =>
      ctx.slots.register(
        {
          name: 'settings.section',
          id: 'huohuo-capabilities',
          order: 12,
          label: '工具与 Skill',
          inject: () => ({
            select: (id: string) => ctx.layout.selectPanel(id),
            start: (prompt: string) => {
              ctx.layout.selectPanel(null)
              ctx.uiWorkspace.startSession(undefined, { agentPreset: 'huohuo', prompt })
            },
          }),
        },
        CapabilitiesSection as any,
      ),
    )
    const visit = (mandate: string, decision: string) => {
      sessionStorage.setItem('huohuo-return', JSON.stringify({ mandate, decision }))
      ctx.layout.selectPanel('huohuo-research')
    }
    ctx.slots.inject('main', () =>
      ctx.slots.register(
        { name: 'main', key: 'huohuo-activity', label: '动态', inject: () => ({ visit }) },
        ActivityPage,
      ),
    )
    ctx.slots.inject('main', () =>
      ctx.slots.register(
        { name: 'main', key: 'huohuo-evolution', label: '验证与演进' },
        StrategyPage,
      ),
    )
    for (const kind of ['framework'] as const)
      ctx.slots.inject('main', () =>
        ctx.slots.register(
          {
            name: 'main',
            key: `huohuo-${kind}`,
            label: '我的框架',
            inject: () => ({ kind }),
          },
          PlannedPage,
        ),
      )
    ctx.slots.inject('main', () =>
      ctx.slots.register(
        {
          name: 'main',
          key: 'huohuo-notifications',
          label: '消推配置',
          inject: () => ({
            visit: (mandate: string, decision: string) => {
              sessionStorage.setItem('huohuo-return', JSON.stringify({ mandate, decision }))
              ctx.layout.selectPanel('huohuo-research')
            },
          }),
        },
        NotificationsPage,
      ),
    )
    ctx.slots.inject('main', () =>
      ctx.slots.register(
        {
          name: 'main',
          key: 'huohuo-investment',
          label: '持仓与自选',
          inject: () => ({ visit: (mandate: string) => visit(mandate, '') }),
        },
        InvestmentPage,
      ),
    )
    ctx.effect(() => {
      const style = document.createElement('style')
      style.dataset.huohuo = 'query'
      style.textContent = __HUOHUO_CSS__
      document.head.append(style)
      return () => style.remove()
    }, '火火样式')
    ctx.effect(brandMetadata, '火火品牌元数据')
    ctx.slots.inject('sidebar.brand.mark', () =>
      ctx.slots.register({ name: 'sidebar.brand.mark', priority: -100 }, BrandMark),
    )
    ctx.slots.inject('sidebar.brand.name', () =>
      ctx.slots.register({ name: 'sidebar.brand.name', priority: -100 }, BrandName),
    )
    ctx.slots.inject('conversation.hero.brand.mark', () =>
      ctx.slots.register({ name: 'conversation.hero.brand.mark', priority: -100 }, BrandMark),
    )
    ctx.slots.inject('main', () =>
      ctx.slots.register(
        {
          name: 'main',
          key: panelId,
          label: '委托查询',
          inject: () => ({
            goChat: () => {
              ctx.layout.selectPanel(null)
              ctx.uiWorkspace.startSession(undefined, { agentPreset: 'huohuo' })
            },
          }),
        },
        ResearchPage,
      ),
    )
    ctx.slots.inject('sidebar.panellist', () =>
      ctx.slots.register(
        { name: 'sidebar.panellist', id: panelId, order: -100, label: '委托查询' },
        QueryIcon,
      ),
    )
  } catch (error) {
    console.error('火火装配失败', error)
    throw error
  }
}
