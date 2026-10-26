import type { ComponentType, ReactNode } from 'react'
import type { ChatList } from './history.js'

type Selector<S> = <T>(select: (state: S) => T) => T
export interface ChatRuntime {
  sessionId?: string
  useSession: Selector<{ openState: string } | undefined>
  useSessions: Selector<ChatList>
  useWorkspaces: Selector<{ archivedSessionIds: readonly string[]; phase: 'pending' | 'ready'; state: string }>
  usePanelInfo: Selector<{ activePanelId: string | null }>
  useConnectionState: Selector<'connected' | 'disconnected' | 'connecting' | undefined>
  renderSlot: (name: string, props: object) => ReactNode
  renderFactorySlot: (name: string, props: object, options?: { slots: Record<string, ComponentType<any>> }) => ReactNode
}

/** Narrow adapter to the published rc2 slot API. Its private type-only packages
 * are not published at rc2; real Loader/browser assembly verifies this face. */
export interface DshUiContext {
  slots: {
    inject(name: string, install: () => () => void): void
    register<P extends object>(options: { name: string; key?: string; id?: string; order?: number;
      priority?: number; label?: string; children?: Record<string, { kind: string; scope: string }>; inject?: () => P }, component: ComponentType<P>): () => void
  }
  layout: { selectPanel(id: string | null): void; toggleSidebar(): void; closeRightbar(): void }
  uiWorkspace: { openSession(id: string): void; startSession(id?: string, options?: { agentPreset: string }): void }
  sessions: { refresh(): Promise<void> }
  connection: { state: { getSnapshot(): unknown; subscribe(fn: () => void): () => void }; reconnect(): void }
  inputTriggers: { registerSource(source: { trigger: string; name: string; candidates: () => Promise<never[]>;
    onPick: () => undefined; matchEnter: (session: unknown, line: string) => Promise<undefined> }): () => void }
  effect(install: () => void | (() => void), label?: string): void
}
