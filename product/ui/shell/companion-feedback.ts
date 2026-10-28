export function latestFailedTurn(rows: readonly { turn: number; failed: boolean }[]) {
  const latest = Math.max(0, ...rows.map((row) => (Number.isFinite(row.turn) ? row.turn : 0)))
  return latest > 0 && rows.some((row) => row.turn === latest && row.failed) ? latest : undefined
}
