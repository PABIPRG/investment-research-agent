import { useEffect, useRef, useState } from 'react'
import { MenuHistory } from './menu-history.js'

const compactQuery = '(max-width: 1100px)'
export function useNavigationMenu() {
  const [compact, setCompact] = useState(() => window.matchMedia(compactQuery).matches)
  const [open, setOpen] = useState(false)
  const owner = useRef<MenuHistory>()
  if (!owner.current) owner.current = new MenuHistory(window.history, crypto.randomUUID(), setOpen)
  useEffect(() => {
    const media = window.matchMedia(compactQuery)
    const resize = () => {
      setCompact(media.matches)
      if (!media.matches) owner.current!.close()
    }
    const pop = () => owner.current!.pop(media.matches)
    media.addEventListener('change', resize)
    window.addEventListener('popstate', pop)
    return () => {
      media.removeEventListener('change', resize)
      window.removeEventListener('popstate', pop)
      owner.current!.close()
    }
  }, [])
  return {
    compact,
    open,
    show: () => owner.current!.open(),
    close: () => owner.current!.close(),
  }
}
