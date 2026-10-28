export type Actions = {
  start: () => void
  openHistory: (id: string) => void
  select: (id: string | null) => void
  reconnect: () => void
}
