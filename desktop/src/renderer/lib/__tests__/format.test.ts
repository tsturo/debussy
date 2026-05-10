import { describe, it, expect, vi, afterEach } from 'vitest'
import { formatElapsed } from '../format'

describe('formatElapsed', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns minutes-only for < 1 hour', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - 3 * 60 * 1000) / 1000) // 3 minutes ago
    expect(formatElapsed(startedAt)).toBe('3m')
  })

  it('returns "0m" when just started', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor(now / 1000) // exactly now
    expect(formatElapsed(startedAt)).toBe('0m')
  })

  it('returns hours and minutes', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - (1 * 60 * 60 + 5 * 60) * 1000) / 1000) // 1h 5m ago
    expect(formatElapsed(startedAt)).toBe('1h 5m')
  })

  it('returns hours-only when minutes are 0', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - 2 * 60 * 60 * 1000) / 1000) // exactly 2h ago
    expect(formatElapsed(startedAt)).toBe('2h')
  })

  it('handles large elapsed times (many hours)', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - (10 * 60 * 60 + 30 * 60) * 1000) / 1000) // 10h 30m
    expect(formatElapsed(startedAt)).toBe('10h 30m')
  })

  it('returns "59m" for 59 minutes', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - 59 * 60 * 1000) / 1000)
    expect(formatElapsed(startedAt)).toBe('59m')
  })

  it('returns "1h" for exactly 60 minutes', () => {
    vi.useFakeTimers()
    const now = Date.now()
    vi.setSystemTime(now)
    const startedAt = Math.floor((now - 60 * 60 * 1000) / 1000)
    expect(formatElapsed(startedAt)).toBe('1h')
  })
})
