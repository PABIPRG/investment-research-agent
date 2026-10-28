import { useEffect, useState } from 'react'
export function useQuiet() {
  const read = () => {
    try {
      return localStorage.getItem('huohuo.quiet') === 'true'
    } catch {
      return false
    }
  }
  const [quiet, setQuiet] = useState(read)
  useEffect(() => {
    const sync = (event: Event) => {
      const value = (event as CustomEvent<boolean>).detail
      setQuiet(typeof value === 'boolean' ? value : read())
    }
    window.addEventListener('huohuo-presence', sync)
    return () => window.removeEventListener('huohuo-presence', sync)
  }, [])
  return {
    quiet,
    toggle: () => {
      try {
        localStorage.setItem('huohuo.quiet', String(!quiet))
      } catch {}
      setQuiet(!quiet)
      window.dispatchEvent(new CustomEvent('huohuo-presence', { detail: !quiet }))
    },
  }
}
