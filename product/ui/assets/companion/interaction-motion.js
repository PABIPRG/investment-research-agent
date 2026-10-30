export function createInteraction(pivot, canvas) {
  let turning = false,
    time = 0
  return {
    tick(dt) {
      if (turning) {
        time = Math.min(time + dt, 0.48)
        const progress = time / 0.48
        pivot.rotation.y = Math.PI * 2 * progress * progress * (3 - 2 * progress)
        if (progress === 1) {
          turning = false
          pivot.rotation.y = 0
          canvas.dataset.turning = 'false'
        }
      }
    },
    turn() {
      turning = true
      time = 0
      canvas.dataset.turning = 'true'
      canvas.dataset.turnCount = String(Number(canvas.dataset.turnCount || 0) + 1)
    },
    reset() {
      turning = false
      pivot.rotation.y = 0
      canvas.dataset.turning = 'false'
    },
  }
}
