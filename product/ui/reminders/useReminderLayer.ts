import { useLayoutEffect, useState, type RefObject } from 'react'
/** Keep the same subtree/canvas. A native modal makes outside popovers inert. */
export function useReminderLayer(ref: RefObject<HTMLDivElement>, active: boolean) {
  const [blocked, setBlocked] = useState(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (!active || !el) return
    const origin = document.createComment('huohuo-reminder-origin')
    el.before(origin)
    el.setAttribute('popover', 'manual')
    const isOpen = () => typeof el.hidePopover === 'function' && el.matches(':popover-open')
    const position = () => {
      const modal = [...document.querySelectorAll<HTMLDialogElement>('dialog[open]')].at(-1)
      const target = modal ?? origin.parentNode
      setBlocked(!!modal)
      if (target && el.parentNode !== target) {
        if (isOpen()) el.hidePopover()
        target.appendChild(el)
      }
      if (typeof el.showPopover === 'function' && !el.matches(':popover-open')) el.showPopover()
    }
    position()
    const observer = new MutationObserver(position)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['open'],
    })
    return () => {
      observer.disconnect()
      if (isOpen()) el.hidePopover()
      if (origin.parentNode) origin.replaceWith(el)
      el.removeAttribute('popover')
      setBlocked(false)
    }
  }, [ref, active])
  return blocked
}
