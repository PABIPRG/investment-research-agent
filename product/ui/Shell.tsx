import { useEffect, useState } from 'react'
import type { ChatRuntime, DshUiContext } from './dsh-face.js'
import { historyRows } from './history.js'
import css from './Shell.module.css'

interface Actions { start: () => void; open: (id: string) => void; chat: () => void; query: () => void; investment: () => void; notifications: () => void; toggle: () => void; reconnect: () => void }
function useDelayed(pending: boolean) {
  const [delayed, setDelayed] = useState(false)
  useEffect(() => { setDelayed(false); if (!pending) return; const timer = setTimeout(() => setDelayed(true), 10000); return () => clearTimeout(timer) }, [pending])
  return delayed
}
function Icon({ kind }: { kind: 'chat' | 'query' | 'history' | 'new' | 'close' }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">{
    kind === 'chat' ? <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z" /> :
    kind === 'query' ? <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></> :
    kind === 'new' ? <path d="M12 4v16M4 12h16"/> : kind === 'history' ? <><path d="M3 11a9 9 0 1 1 2 7M3 5v6h6M12 7v6l4 2"/></> : <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></>
  }</svg>
}
function Sidebar(props: ChatRuntime & Actions & { collapsed: boolean }) {
  const { collapsed, start, open, chat, query, investment, toggle, reconnect } = props
  const list = props.useSessions(s => s)
  const selected = list.ids.find(id => (list.byId[id]?.retainedBy?.mainView ?? 0) > 0)
  const workspaces = props.useWorkspaces(s => s)
  const panel = props.usePanelInfo(s => s.activePanelId)
  const [expanded, setExpanded] = useState(true)
  const connection = props.useConnectionState(s => s)
  const pending = list.phase === 'pending' || workspaces.phase === 'pending'
  const delayed = useDelayed(pending)
  const rows = historyRows(list, workspaces.archivedSessionIds, selected, workspaces.phase === 'ready')
  const disconnected = connection !== 'connected' || workspaces.state === 'error'
  return <aside className={css.sidebar} data-collapsed={collapsed} aria-label="火火导航">
    <div className={css.brand}>{!collapsed && <>{props.renderSlot('sidebar.brand.mark', { size: 32 })}<span className={css.brandText}>{props.renderSlot('sidebar.brand.name', {})}</span></>}
      <button className={css.icon} onClick={toggle} aria-label={collapsed ? '展开导航' : '收起导航'} title={collapsed ? '展开导航' : '收起导航'}><Icon kind="close"/></button></div>
    <section className={css.chatSection} aria-label="AI 对话与历史">
      <div className={css.row}><button className={css.button} onClick={chat} aria-label="AI 对话" title="AI 对话" aria-current={panel === null ? 'page' : undefined}><Icon kind="chat"/>{!collapsed && 'AI 对话'}</button>
        {!collapsed && <button className={css.icon} onClick={start} aria-label="新对话" title="新对话"><Icon kind="new"/></button>}</div>
      {collapsed ? <><button className={css.button} onClick={start} aria-label="新对话" title="新对话"><Icon kind="new"/></button><button className={css.button} onClick={() => { setExpanded(true); toggle() }} aria-label="展开对话历史" title="对话历史"><Icon kind="history"/></button></> : <>
        <button className={css.button} aria-expanded={expanded} aria-controls="huohuo-history" onClick={() => setExpanded(x => !x)}><span aria-hidden="true">{expanded ? '⌄' : '›'}</span>对话历史</button>
        {expanded && <div id="huohuo-history" className={css.historyRegion}>
          {pending && <p className={css.note} role="status">{delayed ? '历史尚未加载完成。' : '正在读取历史…'}</p>}
          {disconnected && <p className={`${css.note} ${css.error}`} role="status">连接暂时不可用，已有内容可能过期。</p>}
          {(disconnected || delayed) && <button className={css.button} onClick={reconnect}>重新连接</button>}
          {!rows.length && !pending && !disconnected && <p className={css.note}>暂无对话历史，点击新对话开始。</p>}
          <ul className={css.history}>{rows.map(row => <li key={row.id}><button className={css.historyButton} title={row.label} data-chat-id={row.id} aria-current={panel === null && selected === row.id ? 'page' : undefined} onClick={() => open(row.id)}><span>{row.label}</span>{row.running && <small>进行中</small>}</button></li>)}</ul>
        </div>}
      </>}
    </section>
    <button className={css.button} onClick={query} aria-label="委托查询" title="委托查询" aria-current={panel === 'huohuo-research' ? 'page' : undefined}><Icon kind="query"/>{!collapsed && '委托查询'}</button>
    <button className={css.button} onClick={investment} aria-label="持仓与自选" title="持仓与自选" aria-current={panel === 'huohuo-investment' ? 'page' : undefined}><Icon kind="query"/>{!collapsed && '持仓与自选'}</button>
    <button className={css.button} onClick={props.notifications} aria-label="消推配置" title="消推配置" aria-current={panel === 'huohuo-notifications' ? 'page' : undefined}><Icon kind="query"/>{!collapsed && '消推配置'}</button>
    <div className={css.foot}>{props.renderSlot('sidebar.settings', { wide: !collapsed })}</div>
  </aside>
}
export function installShell(ctx: DshUiContext) {
  // Keep the native auxiliary panel available to the native conversation header.
  ctx.layout.closeRightbar()
  const start = () => ctx.uiWorkspace.startSession(undefined, { agentPreset: 'huohuo' })
  ctx.slots.inject('sidebar', () => ctx.slots.register({ name: 'sidebar', children: {
    'sidebar.brand.mark': { kind: 'single', scope: 'root' },
    'sidebar.brand.name': { kind: 'single', scope: 'root' },
    'sidebar.settings': { kind: 'single', scope: 'root' },
    'sidebar.panellist': { kind: 'list', scope: 'root' },
  }, inject: () => ({ start, open: (id: string) => ctx.uiWorkspace.openSession(id), chat: () => ctx.layout.selectPanel(null),
    notifications: () => ctx.layout.selectPanel('huohuo-notifications'), query: () => ctx.layout.selectPanel('huohuo-research'), investment: () => ctx.layout.selectPanel('huohuo-investment'), toggle: () => ctx.layout.toggleSidebar(), reconnect: () => ctx.connection.reconnect(), hooks: { connectionState: ctx.connection.state } }) }, Sidebar as any))
  ctx.effect(() => ctx.inputTriggers.registerSource({ trigger: '/', name: 'huohuo-command-boundary', candidates: async () => [], onPick: () => undefined,
    matchEnter: async (_session, line) => { if (/^\/(?:permission|权限|model|模型|plan|计划)(?:\s|$)/i.test(line.trim())) throw new Error('火火已使用固定研究模式；模型配置请前往设置。'); return undefined },
  }), '火火输入边界')
}
