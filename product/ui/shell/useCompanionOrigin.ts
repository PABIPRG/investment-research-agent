import { useLayoutEffect, useRef, type RefObject } from 'react'
import { captureCompanionOrigin, type CompanionOrigin } from './history-transition.js'

/** Read the visible origin before native submit changes the layout; never intercept input. */
export function useCompanionOrigin(root: RefObject<HTMLDivElement>) {
  const origin = useRef<CompanionOrigin>()
  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    const capture = () => {
      const visible = captureCompanionOrigin(el)
      if (visible) origin.current = visible
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
