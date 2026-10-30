import { useLayoutEffect, type RefObject } from 'react'
/** One fixed canvas follows the existing chat anchor; only transforms animate the reminder. */
export function useActorPosition(
  ref: RefObject<HTMLDivElement>,
  options: { reminder: boolean; corner: boolean; chat: boolean; state: string; ready: string },
) {
  useLayoutEffect(() => {
    const actor = ref.current
    if (!actor) return
    let frame = 0,
      root: HTMLElement | null = null
    let lastTransform = ''
    const turn = () => actor.dispatchEvent(new Event('huohuo-companion-travel'))
    const set = (x: number, y: number, height: number) => {
      const transform = `translate3d(${Math.round(x * 2) / 2}px,${Math.round(y * 2) / 2}px,0) scale(${height / 280})`
      if (lastTransform !== transform) {
        lastTransform = transform
        actor.style.transform = transform
      }
      if (actor.style.visibility !== 'visible') actor.style.visibility = 'visible'
    }
    const update = () => {
      frame = 0
      const conversation = document.querySelector<HTMLElement>('[data-huohuo-conversation]')
      if (root !== conversation) {
        root?.removeEventListener('huohuo-companion-travel', turn)
        root = conversation
        root?.addEventListener('huohuo-companion-travel', turn)
      }
      const anchor = conversation?.querySelector<HTMLElement>('[data-huohuo-companion]')
      if (anchor && anchor.dataset.companionModel !== options.ready)
        anchor.dataset.companionModel = options.ready
      if (options.reminder && actor.style.opacity !== '1') actor.style.opacity = '1'
      if (options.reminder && options.corner) {
        const card = document.querySelector<HTMLElement>('[data-huohuo-reminder]')
        if (!card) return
        const rect = card.getBoundingClientRect(),
          height = Math.min(144, innerHeight * 0.22)
        set(
          Math.min(innerWidth - 96, rect.right - 136),
          Math.max(8, rect.top - height + 34),
          height,
        )
        return
      }
      if (options.chat && anchor && getComputedStyle(anchor).visibility !== 'hidden') {
        const opacity = getComputedStyle(anchor).opacity
        if (!options.reminder && actor.style.opacity !== opacity) actor.style.opacity = opacity
        const rect = anchor.getBoundingClientRect()
        if (rect.height > 0) {
          set(rect.left + rect.width / 2 - (rect.height * 240) / 280 / 2, rect.top, rect.height)
          if (anchor.getAnimations().some((a) => a.playState === 'running'))
            frame = requestAnimationFrame(update)
          return
        }
      }
      if (!options.reminder && actor.style.visibility !== 'hidden')
        actor.style.visibility = 'hidden'
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    const observer = new MutationObserver(schedule)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: [
        'data-arrival',
        'data-intro',
        'data-question',
        'data-companion-positioned',
        'data-companion-travel',
        'data-history-transition',
        'data-welcome-transition',
        'style',
      ],
    })
    const resize = new ResizeObserver(schedule)
    resize.observe(document.documentElement)
    const card = document.querySelector<HTMLElement>('[data-huohuo-reminder]')
    if (card) resize.observe(card)
    document.addEventListener('scroll', schedule, true)
    window.addEventListener('resize', schedule)
    update()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      resize.disconnect()
      root?.removeEventListener('huohuo-companion-travel', turn)
      document.removeEventListener('scroll', schedule, true)
      window.removeEventListener('resize', schedule)
    }
  }, [ref, options.reminder, options.corner, options.chat, options.state, options.ready])
}
