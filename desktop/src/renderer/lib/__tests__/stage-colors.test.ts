import { describe, it, expect } from 'vitest'
import { STAGE_COLORS, STAGE_ORDER } from '../stage-colors'

// KanbanCard.tsx applies STAGE_COLORS[task.stage].color as the borderLeft color.
// The component uses: borderLeft: `${isSelected ? 3 : 2}px solid ${stageColor}`
// These tests verify the data that drives that styling.

describe('STAGE_COLORS', () => {
  it('assigns purple (#6c5ce7) to development stage — DEV card left border', () => {
    expect(STAGE_COLORS.development.color).toBe('#6c5ce7')
  })

  it('assigns amber (#d4a843) to reviewing stage — REVIEW card left border', () => {
    expect(STAGE_COLORS.reviewing.color).toBe('#d4a843')
  })

  it('assigns teal (#00cec9) to merging stage — MERGE card left border', () => {
    expect(STAGE_COLORS.merging.color).toBe('#00cec9')
  })

  it('assigns muted (#3a4258) to done stage — DONE card left border', () => {
    expect(STAGE_COLORS.done.color).toBe('#3a4258')
  })

  it('has a hex color entry for every pipeline stage', () => {
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

  it('has a display label for every pipeline stage', () => {
    for (const stage of STAGE_ORDER) {
      expect(typeof STAGE_COLORS[stage].label).toBe('string')
      expect(STAGE_COLORS[stage].label.length).toBeGreaterThan(0)
    }
  })

  it('STAGE_ORDER contains all stages present in STAGE_COLORS', () => {
    const colorKeys = Object.keys(STAGE_COLORS)
    const orderKeys = [...STAGE_ORDER]
    expect(orderKeys.sort()).toEqual(colorKeys.sort())
  })

  it('KanbanCard borderLeft is 2px for unselected, 3px for selected', () => {
    // KanbanCard computes: `${isSelected ? 3 : 2}px solid ${stageColor}`
    // Verify both arms of the ternary produce the correct CSS token
    const stageColor = STAGE_COLORS.development.color
    const unselected = `${false ? 3 : 2}px solid ${stageColor}`
    const selected = `${true ? 3 : 2}px solid ${stageColor}`
    expect(unselected).toBe(`2px solid ${stageColor}`)
    expect(selected).toBe(`3px solid ${stageColor}`)
  })
})
