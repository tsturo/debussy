import { describe, it, expect } from 'vitest'
import { isValidMove } from '../move-validation'

describe('isValidMove', () => {
  // ── Valid moves ────────────────────────────────────────────────────────────

  it('allows backlog → development', () => {
    expect(isValidMove('backlog', 'pending', 'development')).toBe(true)
  })

  it('allows blocked task from any stage → development', () => {
    const stages = ['development', 'reviewing', 'merging', 'backlog', 'security_review'] as const
    for (const stage of stages) {
      expect(isValidMove(stage, 'blocked', 'development')).toBe(true)
    }
  })

  it('allows active development task → backlog', () => {
    expect(isValidMove('development', 'pending', 'backlog')).toBe(true)
    expect(isValidMove('development', 'active', 'backlog')).toBe(true)
  })

  it('allows active reviewing task → backlog', () => {
    expect(isValidMove('reviewing', 'pending', 'backlog')).toBe(true)
  })

  it('allows active merging task → backlog', () => {
    expect(isValidMove('merging', 'pending', 'backlog')).toBe(true)
  })

  // ── Invalid moves ──────────────────────────────────────────────────────────

  it('rejects done → anywhere', () => {
    const targets = ['backlog', 'development', 'reviewing', 'merging', 'done'] as const
    for (const to of targets) {
      expect(isValidMove('done', 'pending', to)).toBe(false)
    }
  })

  it('rejects any → reviewing', () => {
    expect(isValidMove('backlog', 'pending', 'reviewing')).toBe(false)
    expect(isValidMove('development', 'pending', 'reviewing')).toBe(false)
  })

  it('rejects any → merging', () => {
    expect(isValidMove('development', 'pending', 'merging')).toBe(false)
    expect(isValidMove('backlog', 'pending', 'merging')).toBe(false)
  })

  it('rejects any → done', () => {
    expect(isValidMove('development', 'pending', 'done')).toBe(false)
    expect(isValidMove('backlog', 'pending', 'done')).toBe(false)
  })

  it('rejects any → security_review', () => {
    expect(isValidMove('development', 'pending', 'security_review')).toBe(false)
  })

  it('rejects any → acceptance', () => {
    expect(isValidMove('development', 'pending', 'acceptance')).toBe(false)
  })

  it('rejects same-column drag for non-blocked tasks', () => {
    expect(isValidMove('development', 'pending', 'development')).toBe(false)
    expect(isValidMove('backlog', 'pending', 'backlog')).toBe(false)
  })

  it('allows same-column drag for blocked tasks (unblock in place)', () => {
    // A blocked dev task dragged to the dev column = unblock via takt release
    expect(isValidMove('development', 'blocked', 'development')).toBe(true)
  })

  it('rejects blocked → backlog', () => {
    expect(isValidMove('development', 'blocked', 'backlog')).toBe(false)
    expect(isValidMove('reviewing', 'blocked', 'backlog')).toBe(false)
  })
})
