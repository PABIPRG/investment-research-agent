import { useLayoutEffect, useRef, type RefObject } from 'react'
import css from './SlidingPill.module.css'

/** The same selection marker and easing for product navigation and conversation views. */
export function SlidingPill({
  container,
  selected,
}: {
  container: RefObject<HTMLElement>
  selected: string | null
}) {
  const pill = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const indicator = pill.current,
      owner = container.current ?? indicator?.parentElement
    if (!owner || !indicator) return
    let frame = 0
    const position = () => {
      const current = owner.querySelector<HTMLButtonElement>(
        'button[aria-current="page"], button[aria-pressed="true"]',
      )
      if (!current) {
        indicator.hidden = true
        return
      }
      indicator.style.width = `${current.offsetWidth}px`
      indicator.style.transform = `translateX(${current.offsetLeft}px)`
      indicator.hidden = false
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        indicator.dataset.ready = 'true'
      })
    }
    const observer = new ResizeObserver(position)
    observer.observe(owner)
    owner.querySelectorAll('button').forEach((button) => observer.observe(button))
    position()
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [container, selected])
  return <span ref={pill} className={css.pill} data-sliding-pill hidden aria-hidden="true" />
}
