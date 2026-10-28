import { useEffect, useRef } from 'react'
import type { ChatRuntime } from '../dsh-face.js'
import { historyRows } from '../history.js'
import css from './Root.module.css'
import type { Actions } from './types.js'
import { HeaderMark } from './HeaderMark.js'
import { Navigation } from './Navigation.js'
import { MobileNavigation } from './MobileNavigation.js'
import { useNavigationMenu } from './useNavigationMenu.js'
import { useQuiet } from './useQuiet.js'

import { EnvironmentNotice } from './EnvironmentNotice.js'
export function ProductRoot(props: ChatRuntime & Actions) {
  const { quiet, toggle } = useQuiet()
  const menu = useNavigationMenu()
  const panel = props.usePanelInfo((s) => s.activePanelId),
    list = props.useSessions((s) => s),
    workspaces = props.useWorkspaces((s) => s)
  const selected = list.ids.find((id) => (list.byId[id]?.retainedBy?.mainView ?? 0) > 0),
    started = useRef(false)
  useEffect(() => {
    if (list.phase !== 'ready' || workspaces.phase !== 'ready' || started.current) return
    if (selected && list.byId[selected]?.blank) {
      started.current = true
      return
    }
    if (selected || historyRows(list, workspaces.archivedSessionIds).length) {
      started.current = true
      props.start()
    }
    // 空安装由 DSH 初始化默认会话，避免抢占正在进行的导航。
  }, [list.phase, workspaces.phase, selected])
  return (
    <div className={css.root} data-huohuo-navigation="1.4-r1">
      <header className={css.top}>
        <a
          className={css.brand}
          href="#"
          aria-label="火火，回到对话"
          onClick={(e) => {
            e.preventDefault()
            props.select(null)
          }}
        >
          <HeaderMark />
          <span className={css.wordmark}>
            <strong>火火</strong>
            <small>投研智能体</small>
          </span>
        </a>
        {menu.compact ? (
          <MobileNavigation
            {...menu}
            panel={panel}
            select={props.select}
            quiet={quiet}
            toggle={toggle}
            settings={props.renderSlot('sidebar.settings', { wide: true })}
          />
        ) : (
          <>
            <Navigation panel={panel} select={props.select} />
            <button className={css.presence} onClick={toggle}>
              {quiet ? '显示对话火火' : '隐藏对话火火'}
            </button>
            <div className={css.settings}>
              {props.renderSlot('sidebar.settings', { wide: false })}
            </div>
          </>
        )}
      </header>
      <EnvironmentNotice />
    </div>
  )
}
