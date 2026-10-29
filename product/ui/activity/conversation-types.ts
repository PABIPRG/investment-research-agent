export type ChildRecord = {
  id: string
  mode: 'one-shot' | 'continuable' | 'external' | 'unknown'
  createdAt: number
  label?: string
}
export type ConversationProjection = {
  state: 'idle' | 'loading' | 'ready' | 'migration-required' | 'error'
  values: {
    subagentCatalog?: readonly ChildRecord[]
    subagentTiming?: { lastTurnCompleted?: boolean }
  }
}
export type ConversationStatus = { running?: boolean; pendingInteraction?: unknown }
