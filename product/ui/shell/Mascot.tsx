import { useEffect, useRef, useState } from 'react'
import { companionMotion } from '../companion-state.js'
import css from './Companion.module.css'
// Reuse the rendered projection during remounts, rather than a differently framed illustration.
let modelPoster: string | undefined
export function Mascot({
  motion,
  arrival,
  visible = true,
  onState,
}: {
  motion: ReturnType<typeof companionMotion>
  arrival: boolean
  visible?: boolean
  onState?: (state: string) => void
}) {
  const requestedVisible = useRef(visible)
  requestedVisible.current = visible
  const requestedMotion = useRef(motion)
  requestedMotion.current = motion
  const canvas = useRef<HTMLCanvasElement>(null),
    player = useRef<{
      play: (name: string) => void
      turn: () => void
      setVisible: (visible: boolean) => void
      dispose: () => void
    }>(),
    lastTurn = useRef(-Infinity),
    introStarted = useRef(0),
    [ready, setReady] = useState(false),
    [failed, setFailed] = useState(false)
  useEffect(() => {
    let cancelled = false
    const url = new URL('api/huohuo/companion/renderer.js', document.baseURI).href
    import(/* @vite-ignore */ url)
      .then(async (module) => {
        if (cancelled) return
        const instance = await module.mount(
          canvas.current,
          (poster?: string) => {
            if (poster) modelPoster = poster
            if (!cancelled) setReady(true)
          },
          () => {
            if (!cancelled) {
              setFailed(true)
              setReady(false)
            }
          },
        )
        if (cancelled) instance.dispose()
        else {
          player.current = instance
          instance.play(requestedMotion.current)
          instance.setVisible(requestedVisible.current)
        }
      })
      .catch(() => setFailed(true))
    return () => {
      cancelled = true
      player.current?.dispose()
      player.current = undefined
    }
  }, [])
  useEffect(() => {
    player.current?.play(motion)
  }, [motion])
  useEffect(() => {
    onState?.(ready ? 'ready' : failed ? 'failed' : 'loading')
  }, [ready, failed, onState])
  useEffect(() => {
    player.current?.setVisible(visible)
  }, [visible])
  const turn = () => {
    const now = performance.now()
    if (now - lastTurn.current < 750 || !player.current) return
    lastTurn.current = now
    player.current.turn()
  }
  useEffect(() => {
    if (arrival) introStarted.current = performance.now()
  }, [arrival])
  useEffect(() => {
    if (!arrival || !ready) return
    const timer = window.setTimeout(
      turn,
      Math.max(0, 1610 - (performance.now() - introStarted.current)),
    )
    return () => window.clearTimeout(timer)
  }, [arrival, ready])
  useEffect(() => {
    const root = canvas.current?.closest('[data-huohuo-global-companion]')
    root?.addEventListener('huohuo-companion-travel', turn)
    return () => root?.removeEventListener('huohuo-companion-travel', turn)
  }, [])
  return (
    <div
      className={css.mascot}
      data-motion={motion}
      data-companion-model={ready ? 'ready' : failed ? 'failed' : 'loading'}
      role="img"
      aria-label={`火火 · ${{ sigh: '轻叹后继续陪你', idle: '在这里', listening: '聆听', thinking: '咬笔思考', working: '查阅与整理资料', speaking: '回应中', awaiting_reply: '等待你的回答', gentle_knock: '轻敲窗户' }[motion]}`}
    >
      <canvas ref={canvas} hidden={!ready || failed} />
      {!ready && !failed && modelPoster && <img data-model-poster src={modelPoster} alt="" />}
      {failed && <img src="api/huohuo/companion/fallback.png" alt="" />}
    </div>
  )
}
