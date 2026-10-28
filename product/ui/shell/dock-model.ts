export interface DockAnchor {
  key: string
  turn: number
  kind: string
  part?: string | null
  visible: boolean
}
/** One assistant origin per Turn. Streaming chunks and later steps never retarget it. */
export function responseAnchor(anchors: readonly DockAnchor[]): DockAnchor | undefined {
  const turns = anchors.filter((a) => Number.isFinite(a.turn) && a.turn > 0)
  const latest = Math.max(0, ...turns.map((a) => a.turn))
  const current = turns.filter((a) => a.turn === latest)
  return (
    current.find((a) => a.kind === 'turn-process') ??
    current.find((a) => a.part === 'response' && a.visible) ??
    current.find((a) => a.kind === 'user' && a.visible)
  )
}
export function dockPoint(input: {
  x: number
  y: number
  bodyWidth: number
  bodyHeight: number
  width: number
  height: number
  composerTop?: number
}) {
  const bottom = Math.min(input.bodyHeight, input.composerTop ?? input.bodyHeight)
  return {
    left: Math.max(4, Math.min(input.x - input.width - 12, input.bodyWidth - input.width - 4)),
    top: Math.max(8, Math.min(input.y, bottom - input.height - 12)),
  }
}
