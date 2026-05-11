// Drag & drop move validation for the kanban board.
// Encodes the pipeline rules: which cross-column moves are user-controllable
// vs pipeline-controlled.

import type { Stage, Status } from '../../shared/types'

/**
 * Stages that are entirely pipeline-controlled — users may not drag tasks here.
 */
const PIPELINE_CONTROLLED: Stage[] = [
  'reviewing',
  'security_review',
  'merging',
  'acceptance',
  'done',
]

/**
 * Returns true when a task may be dragged from `fromStage` (with `status`) to
 * `toStage`.
 *
 * Valid moves:
 *  - backlog → development  (non-blocked backlog tasks)
 *  - blocked (any stage) → development
 *  - any active (non-done, non-blocked, non-backlog) stage → backlog
 */
export function isValidMove(
  fromStage: Stage,
  status: Status,
  toStage: Stage,
): boolean {
  // Done tasks are permanently settled — never moveable
  if (fromStage === 'done') return false

  // Pipeline-controlled targets are off limits
  if (PIPELINE_CONTROLLED.includes(toStage)) return false

  // Blocked tasks: the only valid action is unblocking to development.
  // This includes same-column drops (e.g. blocked dev task → dev column = unblock).
  if (status === 'blocked') {
    return toStage === 'development'
  }

  // Non-blocked, same-column drag — nothing to do
  if (fromStage === toStage) return false

  // Backlog tasks can only be advanced to development
  if (fromStage === 'backlog') {
    return toStage === 'development'
  }

  // Active pipeline tasks (development, reviewing, etc.) can be parked to backlog
  return toStage === 'backlog'
}

/**
 * Human-readable label for a stage transition, used in the confirmation dialog.
 */
export const STAGE_LABELS: Record<Stage, string> = {
  backlog:         'Backlog',
  development:     'Development',
  reviewing:       'Reviewing',
  security_review: 'Security Review',
  merging:         'Merging',
  acceptance:      'Acceptance',
  done:            'Done',
}
