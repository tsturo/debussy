/**
 * Formats elapsed time since a Unix timestamp into a human-readable string.
 *
 * Examples: "just now", "2m", "1h 30m", "3d"
 */
export function formatElapsed(startedAt: number): string {
  const seconds = Math.floor((Date.now() - startedAt * 1000) / 1000)

  if (seconds < 60) return 'just now'

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  if (hours < 24) {
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
  }

  const days = Math.floor(hours / 24)
  return `${days}d`
}
