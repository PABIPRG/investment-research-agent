/** DSH turn identity, not streamed node identity, decides when the companion travels. */
export class ReplyTurnTracker {
  private sessionId?: string
  private turn = 0
  visit(sessionId: string | undefined, turn: number | undefined) {
    if (!sessionId || !turn || !Number.isFinite(turn)) return false
    const sameSession = this.sessionId === sessionId
    const changed = sameSession && this.turn > 0 && turn > this.turn
    this.turn = sameSession ? Math.max(this.turn, turn) : turn
    this.sessionId = sessionId
    return changed
  }
}
