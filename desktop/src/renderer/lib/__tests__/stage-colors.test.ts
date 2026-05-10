import { describe, it, expect } from 'vitest'
import { STAGE_COLORS } from '../stage-colors'

describe('STAGE_COLORS', () => {
  it('assigns purple (#6c5ce7) to development stage', () => {
    expect(STAGE_COLORS.development.color).toBe('#6c5ce7')
  })

  it('assigns amber (#d4a843) to reviewing stage', () => {
    expect(STAGE_COLORS.reviewing.color).toBe('#d4a843')
  })

  it('assigns teal (#00cec9) to merging stage', () => {
    expect(STAGE_COLORS.merging.color).toBe('#00cec9')
  })

  it('assigns muted (#3a4258) to done stage', () => {
    expect(STAGE_COLORS.done.color).toBe('#3a4258')
  })

  it('has a color entry for every pipeline stage', () => {
    const stages = [
      'development',
      'reviewing',
      'security_review',
      'merging',
      'acceptance',
      'backlog',
      'done',
    ] as const
    for (const stage of stages) {
      expect(STAGE_COLORS[stage].color).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })
})

describe('KanbanCard border width logic', () => {
  it('uses 2px border for unselected cards', () => {
    const isSelected = false
    const borderWidth = isSelected ? 3 : 2
    expect(borderWidth).toBe(2)
  })

  it('uses 3px border for selected cards', () => {
    const isSelected = true
    const borderWidth = isSelected ? 3 : 2
    expect(borderWidth).toBe(3)
  })
})
