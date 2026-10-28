type HistoryPort = Pick<History, 'state' | 'pushState' | 'back'>

/** One transient entry makes the browser Back action dismiss the drawer first. */
export class MenuHistory {
  private openState = false
  private restoring = false
  constructor(
    private history: HistoryPort,
    private key: string,
    private change: (open: boolean) => void,
  ) {}
  private owns() {
    return this.history.state?.huohuoNavigationDrawer === this.key
  }
  open() {
    if (this.openState || this.restoring) return
    this.history.pushState({ ...this.history.state, huohuoNavigationDrawer: this.key }, '')
    this.openState = true
    this.change(true)
  }
  close() {
    if (!this.openState) return
    this.openState = false
    this.change(false)
    if (this.owns()) {
      this.restoring = true
      this.history.back()
    }
  }
  pop(eligible = true) {
    this.restoring = false
    const next = eligible && this.owns()
    if (next !== this.openState) {
      this.openState = next
      this.change(next)
    }
  }
}
