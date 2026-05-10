// Pipeline stage color tokens and display labels.
// Colors use Tonale palette values. Column order matches board.py BOARD_COLUMNS.

import type { Stage } from '../../shared/types'

export interface StageDisplay {
  color: string
  label: string
}

/** Maps each pipeline stage to its Tonale color token and display label. */
export const STAGE_COLORS: Record<Stage, StageDisplay> = {
  development:     { color: '#6c5ce7', label: 'DEV' },
  reviewing:       { color: '#d4a843', label: 'REVIEW' },
  security_review: { color: '#b39ddb', label: 'SEC REVIEW' },
  merging:         { color: '#00cec9', label: 'MERGE' },
  acceptance:      { color: '#d4a843', label: 'ACCEPT' },
  backlog:         { color: '#6b7388', label: 'BACKLOG' },
  done:            { color: '#3a4258', label: 'DONE' },
}

/**
 * Stage order for Kanban column rendering.
 * Matches the column order defined in src/debussy/board.py BOARD_COLUMNS.
 */
export const STAGE_ORDER: Stage[] = [
  'development',
  'reviewing',
  'security_review',
  'merging',
  'acceptance',
  'backlog',
  'done',
]
