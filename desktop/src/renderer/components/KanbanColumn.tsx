import { useDroppable } from '@dnd-kit/core'
import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { KanbanCard } from './KanbanCard'

export interface ActiveDragData {
  taskId: string
  fromStage: Stage
  isBlocked: boolean
}

export interface KanbanColumnProps {
  stage: Stage
  tasks: Task[]
  agents: Map<string, { name: string; stage: Stage }>
  selectedTaskId: string | null
  onCardClick: (taskId: string) => void
  /** Drag state from the active drag — null when nothing is being dragged. */
  activeDragData: ActiveDragData | null
}

/** Column opacity by stage — done and backlog are visually de-emphasized. */
function columnOpacity(stage: Stage): number {
  if (stage === 'done') return 0.6
  if (stage === 'backlog') return 0.25
  return 1
}

/**
 * Returns true if a card being dragged from `fromStage` (with blocked status)
 * can validly be dropped onto `targetStage`.
 *
 * Valid moves:
 * - backlog → development
 * - blocked (any stage) → development
 * - any non-done, non-backlog stage → backlog
 */
function isValidDropTarget(targetStage: Stage, drag: ActiveDragData): boolean {
  const { fromStage, isBlocked } = drag
  if (targetStage === fromStage) return false
  if (fromStage === 'done') return false

  if (fromStage === 'backlog' && targetStage === 'development') return true
  if (isBlocked && targetStage === 'development') return true
  if (targetStage === 'backlog' && fromStage !== 'done' && fromStage !== 'backlog') return true

  return false
}

export function KanbanColumn({
  stage,
  tasks,
  agents,
  selectedTaskId,
  onCardClick,
  activeDragData,
}: KanbanColumnProps) {
  const { color, label } = STAGE_COLORS[stage]

  const { setNodeRef, isOver } = useDroppable({
    id: `col-${stage}`,
    data: { targetStage: stage },
  })

  const isValid = activeDragData !== null && isValidDropTarget(stage, activeDragData)
  const isInvalid = activeDragData !== null && isOver && !isValid

  // Highlight border: purple tint when valid target is hovered, red tint when invalid
  const dropBorderColor = isOver && isValid
    ? '#6c5ce733'
    : isInvalid
    ? 'rgba(217,112,112,0.25)'
    : 'transparent'

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: 1,
        minWidth: '140px',
        display: 'flex',
        flexDirection: 'column',
        opacity: columnOpacity(stage),
        borderRadius: 'var(--t-radius-md)',
        border: `1.5px solid ${dropBorderColor}`,
        padding: '2px',
        transition: 'border-color 150ms ease',
        boxSizing: 'border-box',
      }}
    >
      {/* Column header: label + count on one line */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '4px',
        }}
      >
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color,
            letterSpacing: '0.04em',
            lineHeight: 1,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: 'var(--t-text-3)',
            lineHeight: 1,
          }}
        >
          {tasks.length}
        </span>
      </div>

      {/* Cards area */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          overflowY: 'auto',
          flex: 1,
          minHeight: '60px',
        }}
      >
        {tasks.map((task) => {
          const agentInfo = agents.get(task.id) ?? null
          const agent = agentInfo
            ? { name: agentInfo.name, stage: agentInfo.stage }
            : null

          return (
            <KanbanCard
              key={task.id}
              task={task}
              agent={agent}
              isSelected={task.id === selectedTaskId}
              onClick={() => onCardClick(task.id)}
              draggable={task.stage !== 'done'}
            />
          )
        })}
      </div>
    </div>
  )
}
