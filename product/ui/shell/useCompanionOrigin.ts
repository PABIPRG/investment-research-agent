import { useLayoutEffect, useRef, type RefObject } from 'react'

/** Read the visible origin before native submit changes the layout; never intercept input. */
export function useCompanionOrigin(root: RefObject<HTMLDivElement>) {
  const origin = useRef<DOMRect>()
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const capture = () => {
      if (el.dataset.arrival !== 'true') return
      const dock = el.querySelector<HTMLElement>('[data-huohuo-companion]')
      if (dock) origin.current = dock.getBoundingClientRect()
    }
    el.addEventListener('keydown', capture, true)
    el.addEventListener('click', capture, true)
    return () => {
      el.removeEventListener('keydown', capture, true)
      el.removeEventListener('click', capture, true)
    }
  }, [root])
  return origin
}
