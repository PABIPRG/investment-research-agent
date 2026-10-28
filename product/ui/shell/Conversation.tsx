import page from '../shared/Page.module.css'
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { companionMotion } from '../companion-state.js'
import type { ChatRuntime } from '../dsh-face.js'
import type { MandateView } from '../mandates/model.js'
import { Account } from './Account.js'
import { Arrival } from './Arrival.js'
import motionCss from './Companion.module.css'
import introCss from './Intro.module.css'
import css from './Conversation.module.css'
import { History } from './History.js'
import { isHistoryTransition } from './history-transition.js'
import { Mascot } from './Mascot.js'
import type { Actions } from './types.js'
import { ViewTabs } from './ViewTabs.js'
import { useConversationFeedback } from './useConversationFeedback.js'
import { useCompanionDock } from './useCompanionDock.js'
import { useQuiet } from './useQuiet.js'
import { beginWelcomeTransition } from './welcome-transition.js'
import { conversationActivity } from './companion-feedback.js'
const View = createContext<'chat' | 'trajectory'>('chat')
function NativeViews(props: ChatRuntime) {
  const view = useContext(View)
  return props.renderSlot('conversation.session', { view })
}
const contentSlots = { views: NativeViews }
let introPlayed = false
export function Conversation(props: ChatRuntime & Actions) {
  const { quiet } = useQuiet(),
    [history, setHistory] = useState(false),
    [view, setView] = useState<'chat' | 'trajectory'>('chat')
  const session = props.useSession((s) => s),
    status = props.useSessionStatus((s) => (props.sessionId ? s.get(props.sessionId) : undefined)),
    input = props.useInput((s) => s)
  const hasTrajectory = props.useTrajectory((s) =>
    Boolean(
      s.eventNodes.length ||
        s.requests.length ||
        s.partial ||
        s.runningCalls.length ||
        s.systemPrompts?.length,
    ),
  )
  const activityPhase = props.useTrajectory(conversationActivity)
  useEffect(() => {
    if (!hasTrajectory) setView('chat')
  }, [hasTrajectory, props.sessionId])
  const blank = session?.blank === true || (!session && !props.sessionId),
    pending = !!status?.pendingInteraction
  const historyLoading =
    isHistoryTransition(props.sessionId) && (!session || session.openState === 'loading')
  const [intro, setIntro] = useState(false)
  useLayoutEffect(() => {
    if (
      blank &&
      Boolean(props.sessionId && session?.openState === 'open' && session.blank) &&
      !introPlayed &&
      !quiet &&
      view === 'chat' &&
      !isHistoryTransition(props.sessionId)
    ) {
      introPlayed = true
      setIntro(true)
    }
    if (!blank) setIntro(false)
  }, [blank, quiet, view, props.sessionId, session?.openState, session?.blank])
  const [activity, setActivity] = useState<MandateView[]>([]),
    [loadError, setLoadError] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const { failed } = useConversationFeedback(
    root,
    props.sessionId,
    Boolean(input?.draft?.trim() || pending),
  )
  useEffect(() => {
    const abort = new AbortController()
    fetch('api/huohuo/mandates', { signal: abort.signal, cache: 'no-store' })
      .then((r) => {
        if (!r.ok) throw Error()
        return r.json()
      })
      .then((data) => setActivity(data.items))
      .catch(() => {
        if (!abort.signal.aborted) setLoadError(true)
      })
    return () => abort.abort()
  }, [props.sessionId])
  useCompanionDock(root, {
    sessionId: props.sessionId,
    blank,
    pending,
    quiet,
    view,
    openState: session?.openState,
  })
  const motion = companionMotion({
    pending,
    running: status?.running,
    streaming: Boolean(status?.running && activityPhase === 'speaking'),
    working: activityPhase === 'working',
    failed,
    draft: input?.draft,
  })
  return (
    <View.Provider value={view}>
      <section
        ref={root}
        className={`${page.surface} ${css.conversation}`}
        data-huohuo-conversation
        data-view={view}
        data-arrival={blank && view === 'chat'}
        data-intro={intro && blank && view === 'chat'}
        data-question={pending}
        data-history-loading={historyLoading}
        data-quiet={quiet}
        aria-label="与火火的对话"
      >
        <header className={`${page.header} ${css.chatHead}`}>
          <div className={css.heading}>
            <h1 className={page.srOnly}>与火火的对话</h1>
            {hasTrajectory && <ViewTabs view={view} select={setView} />}
          </div>
          {status?.running && (
            <span className={css.muted} role="status">
              正在处理
            </span>
          )}
          <div className={css.chatActions}>
            <button
              onClick={() => {
                const dock = root.current?.querySelector<HTMLElement>('[data-huohuo-companion]')
                if (
                  !blank &&
                  !quiet &&
                  view === 'chat' &&
                  dock &&
                  getComputedStyle(dock).visibility !== 'hidden'
                )
                  beginWelcomeTransition(dock.getBoundingClientRect())
                props.start()
              }}
            >
              新对话
            </button>
            <button onClick={() => setHistory(true)}>历史对话</button>
          </div>
        </header>
        <div className={css.chatBody} data-huohuo-chat-body>
          {intro && blank && view === 'chat' && !quiet && !isHistoryTransition(props.sessionId) && (
            <>
              <div className={introCss.iris} aria-hidden="true" />
              <div className={introCss.message} data-huohuo-intro-message aria-hidden="true">
                火火，你的投研好伙伴
              </div>
            </>
          )}
          {blank && view === 'chat' && <Account select={props.select} />}
          {!quiet && view === 'chat' && (
            <div className={motionCss.dock} data-huohuo-companion>
              <Mascot
                motion={motion}
                arrival={intro && blank && !isHistoryTransition(props.sessionId)}
              />
            </div>
          )}
          {historyLoading && (
            <p className={css.historyLoading} role="status">
              正在打开对话…
            </p>
          )}
          {blank && view === 'chat' && (
            <Arrival
              select={props.select}
              input={input}
              inputActions={props.inputActions}
              items={activity}
              error={loadError}
            />
          )}
          <div className={css.native}>
            {props.renderFactorySlot(
              'conversation.content',
              { variant: 'embedded', phase: blank ? 'hero' : 'active', hero: false },
              { slots: contentSlots },
            )}
          </div>
        </div>
        {history && <History {...props} fromWelcome={blank} close={() => setHistory(false)} />}
      </section>
    </View.Provider>
  )
}
