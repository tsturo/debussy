import { useEffect, useState } from 'react'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])
  return matches
}

export function useBreakpoint() {
  const isLarge = useMediaQuery('(min-width: 1680px)')
  const isMedium = useMediaQuery('(min-width: 1366px)')
  return { isLarge, isMedium }
}
