import { useEffect, useRef, useState, type RefObject } from 'react'
import { latestFailedTurn } from './companion-feedback.js'

const expressed = new Set<string>()
/** Read native rendered failure state, not model prose or older failures in the transcript. */
export function useConversationFeedback(
  root: RefObject<HTMLDivElement>,
  sessionId: string | undefined,
  interacting: boolean,
) {
  const interaction = useRef(interacting)
  interaction.current = interacting
  const [streaming, setStreaming] = useState(false),
    [failed, setFailed] = useState(false)
  useEffect(() => {
    if (interacting) setFailed(false)
  }, [interacting])
  useEffect(() => {
    const el = root.current
    if (!el) return
    let timer = 0
    setFailed(false)
    const update = () => {
      setStreaming(!!el.querySelector('[data-streaming="true"]'))
      const turn = latestFailedTurn(
        Array.from(el.querySelectorAll<HTMLElement>('[data-chat-turn]')).map((node) => ({
          turn: Number(node.dataset.chatTurn),
          failed: !!node.querySelector('[data-huohuo-failure]'),
        })),
      )
      if (!turn || !sessionId) {
        setFailed(false)
        return
      }
      const key = `${sessionId}:${turn}`
      if (expressed.has(key)) return
      expressed.add(key)
      if (expressed.size > 100) expressed.delete(expressed.values().next().value!)
      if (interaction.current) return
      clearTimeout(timer)
      setFailed(true)
      timer = window.setTimeout(() => setFailed(false), 1800)
    }
    const observer = new MutationObserver(update)
    observer.observe(el, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-streaming', 'data-chat-turn'],
    })
    update()
    return () => {
      clearTimeout(timer)
      observer.disconnect()
    }
  }, [root, sessionId])
  return { streaming, failed }
}
