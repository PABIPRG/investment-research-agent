/** Only in-flight DSH projection counts; a reasoning block is not a spoken reply. */
export function conversationActivity(input: {
  partial: unknown
  runningCalls: readonly unknown[]
}): 'thinking' | 'working' | 'speaking' | undefined {
  if (
    input.runningCalls.some(
      (call) => call && typeof call === 'object' && 'phase' in call && call.phase === 'start',
    )
  )
    return 'working'
  const partial = input.partial
  if (
    !partial ||
    typeof partial !== 'object' ||
    !('blocks' in partial) ||
    !Array.isArray(partial.blocks)
  )
    return undefined
  const tail = partial.blocks.at(-1)
  if (!tail || typeof tail !== 'object') return undefined
  if (tail.kind === 'reasoning' || tail.kind === 'tool-call') return 'thinking'
  if (tail.kind === 'text' && typeof tail.text === 'string' && tail.text.trim()) return 'speaking'
  return undefined
}

export function latestFailedTurn(rows: readonly { turn: number; failed: boolean }[]) {
  const latest = Math.max(0, ...rows.map((row) => (Number.isFinite(row.turn) ? row.turn : 0)))
  return latest > 0 && rows.some((row) => row.turn === latest && row.failed) ? latest : undefined
}
