import type { DshUiContext } from './dsh-face.js'
const views: Record<string, string | null> = {
  chat: null,
  mandates: 'huohuo-research',
  investment: 'huohuo-investment',
  notifications: 'huohuo-notifications',
  activity: 'huohuo-activity',
  evolution: 'huohuo-evolution',
}
export function parseProductLink(hash: string) {
  const params = new URLSearchParams(hash.replace(/^#/, '')),
    view = params.get('huohuo-view'),
    mandate = params.get('mandate')
  if (
    !view ||
    !Object.hasOwn(views, view) ||
    [...params.keys()].some((k) => !['huohuo-view', 'mandate'].includes(k)) ||
    params.getAll('huohuo-view').length !== 1 ||
    params.getAll('mandate').length > 1
  )
    return null
  if (mandate && (view !== 'mandates' || !/^MND_[a-f0-9]{32}$/.test(mandate))) return null
  return { view, mandate }
}
export function canonicalProductHref(href: string, base: string) {
  try {
    const current = new URL(base),
      url = new URL(href, current)
    if (
      ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) &&
      url.origin !== current.origin &&
      url.pathname === '/' &&
      !url.search &&
      parseProductLink(url.hash)
    )
      return new URL('/' + url.hash, current.origin).href
    return url.href
  } catch {
    return href
  }
}
export function installProductNavigation(ctx: DshUiContext) {
  ctx.effect(() => {
    const repair = (node: Element) => {
      const links = node.matches('a[href]') ? [node] : [...node.querySelectorAll('a[href]')]
      for (const a of links) {
        const href = a.getAttribute('href')!
        const next = canonicalProductHref(href, window.location.href)
        try {
          if (new URL(href, location.href).href !== next) a.setAttribute('href', next)
        } catch {
          /* Malformed third-party links never interrupt product navigation. */
        }
      }
    }
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'attributes' && record.target instanceof Element) repair(record.target)
        for (const node of record.addedNodes) if (node instanceof Element) repair(node)
      }
    })
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['href'],
    })
    repair(document.body)
    const open = (hash: string) => {
      const target = parseProductLink(hash)
      if (!target) return false
      if (target.mandate) {
        sessionStorage.setItem('huohuo-return', JSON.stringify({ mandate: target.mandate }))
        window.dispatchEvent(new CustomEvent('huohuo-mandate-view', { detail: target.mandate }))
      }
      ctx.layout.selectPanel(views[target.view])
      return true
    }
    const click = (event: MouseEvent) => {
      const a = (event.target as Element)?.closest?.('a[href]')
      if (!a || event.button !== 0 || event.metaKey || event.ctrlKey) return
      let url: URL
      try {
        url = new URL(a.getAttribute('href')!, window.location.href)
      } catch {
        return
      }
      if (
        url.origin === window.location.origin &&
        url.pathname === window.location.pathname &&
        open(url.hash)
      ) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    const hash = () => {
      open(window.location.hash)
    }
    document.addEventListener('click', click, true)
    window.addEventListener('hashchange', hash)
    hash()
    return () => {
      observer.disconnect()
      document.removeEventListener('click', click, true)
      window.removeEventListener('hashchange', hash)
    }
  }, '火火受控页面入口')
}
