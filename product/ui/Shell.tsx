import type { DshUiContext } from './dsh-face.js'
import { Conversation } from './shell/Conversation.js'
import './shell/Dsh.module.css'
import { EnvironmentNotice } from './shell/EnvironmentNotice.js'
import { TurnFailure, TurnProcess } from './shell/TurnFailure.js'
import { ProductRoot } from './shell/ProductRoot.js'
export function installShell(ctx: DshUiContext) {
  ctx.layout.closeRightbar()
  for (const [key, component] of [
    ['turn-error', TurnFailure],
    ['turn-process', TurnProcess],
  ] as const) {
    ctx.slots.inject('conversation.chat.node', () =>
      ctx.slots.register({ name: 'conversation.chat.node', key, priority: -100 }, component as any),
    )
  }
  ctx.slots.inject('settings.models.footer', () =>
    ctx.slots.register(
      { name: 'settings.models.footer', id: 'huohuo-environment' },
      EnvironmentNotice,
    ),
  )
  const actions = () => ({
    start: () => ctx.uiWorkspace.startSession(undefined, { agentPreset: 'huohuo' }),
    openHistory: (id: string) => ctx.uiWorkspace.openSession(id),
    select: (id: string | null) => ctx.layout.selectPanel(id),
    reconnect: () => ctx.connection.reconnect(),
    hooks: { connectionState: ctx.connection.state },
  })
  ctx.effect(() => {
    document.documentElement.dataset.huohuoUi = '1.4-r1'
    return () => {
      delete document.documentElement.dataset.huohuoUi
    }
  }, '火火布局适配')
  ctx.slots.inject('sidebar', () =>
    ctx.slots.register(
      {
        name: 'sidebar',
        priority: -100,
        children: { 'sidebar.settings': { kind: 'single', scope: 'root' } },
        inject: actions,
      },
      ProductRoot as any,
    ),
  )
  ctx.slots.inject('main.conversation', () =>
    ctx.slots.register(
      { name: 'main.conversation', priority: -100, inject: actions },
      Conversation as any,
    ),
  )
  ctx.effect(
    () =>
      ctx.inputTriggers.registerSource({
        trigger: '/',
        name: 'huohuo-command-boundary',
        candidates: async () => [],
        onPick: () => undefined,
        matchEnter: async (_session, line) => {
          if (/^\/(?:permission|权限|model|模型|plan|计划)(?:\s|$)/i.test(line.trim()))
            throw new Error('火火已使用固定研究模式；模型配置请前往设置。')
          return undefined
        },
      }),
    '火火输入边界',
  )
}
