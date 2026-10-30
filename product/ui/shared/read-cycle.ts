/** A late read cannot replace a committed write or a newer read. */
export class ReadCycle {
  private active?: AbortController
  private generation = 0
  begin() {
    this.invalidate()
    const controller = new AbortController()
    this.active = controller
    const generation = this.generation
    return {
      signal: controller.signal,
      current: () => !controller.signal.aborted && generation === this.generation,
      finish: () => {
        if (this.active === controller) this.active = undefined
      },
    }
  }
  get pending() {
    return !!this.active
  }
  invalidate() {
    this.generation++
    this.active?.abort()
    this.active = undefined
  }
}
