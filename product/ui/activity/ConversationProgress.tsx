import { useEffect, useState, useSyncExternalStore } from 'react'
import type { ChatRuntime, DshUiContext } from '../dsh-face.js'
import { conversationProgress } from './conversation-model.js'
export type ConversationProgressProps = Pick<
  ChatRuntime,
  'useSessions' | 'useSessionStatus' | 'useWorkspaces'
> & {
  connectionState: DshUiContext['connection']['state']
  openConversation: (id: string) => void
  refreshConversations: (ids: string[]) => Promise<void>
}
/** DSH remains the sole owner of conversation progress and pending interactions. */
export function useConversationProgress(props: ConversationProgressProps, refresh: number) {
  const list = props.useSessions((s) => s),
    statuses = props.useSessionStatus((s) => s),
    connection = useSyncExternalStore(
      (fn) => props.connectionState.subscribe(fn),
      () => props.connectionState.getSnapshot(),
    ),
    workspaces = props.useWorkspaces((s) => s)
  const [error, setError] = useState(false)
  const model = conversationProgress(list, statuses, {
    connected: connection === 'connected',
    archiveReady: workspaces.phase === 'ready',
    archived: workspaces.archivedSessionIds,
  })
  const key = JSON.stringify(model.refreshIds)
  useEffect(() => {
    if (connection !== 'connected' || !model.ready) return
    let active = true
    setError(false)
    void props.refreshConversations(JSON.parse(key)).catch(() => {
      if (active) setError(true)
    })
    return () => {
      active = false
    }
  }, [connection, model.ready, key, props.refreshConversations, refresh])
  return { ...model, error, connected: connection === 'connected' }
}
