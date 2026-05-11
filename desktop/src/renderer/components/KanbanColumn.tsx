import { useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { KanbanCard } from './KanbanCard'

const DONE_COLLAPSE_THRESHOLD = 20
const DONE_DEFAULT_VISIBLE = 15

export interface KanbanColumnProps {
  stage: Stage
  tasks: Task[]
  agents: Map<string, { name: string; stage: Stage }>
  selectedTaskId: string | null
  onCardClick: (taskId: string) => void
  /** Whether an active drag can validly be dropped here */
  isValidDropTarget?: boolean
  /** Whether an active drag is currently hovering this column */
  isDragOver?: boolean
  /** Whether the column is wide (has tasks, flex: 1) vs narrow (empty, 80px) */
  isWide?: boolean
}

/** Column opacity by stage — done and backlog are visually de-emphasized. */
function columnOpacity(stage: Stage): number {
  if (stage === 'done') return 0.6
  if (stage === 'backlog') return 0.25
  return 1
}

export function KanbanColumn({
  stage,
  tasks,
  agents,
  selectedTaskId,
  onCardClick,
  isValidDropTarget = false,
  isDragOver = false,
  isWide = true,
}: KanbanColumnProps) {
  const { color, label } = STAGE_COLORS[stage]
  const [doneExpanded, setDoneExpanded] = useState(false)

  const isDone = stage === 'done'
  const cardGap = isDone ? '6px' : '4px'

  const visibleTasks =
    isDone && !doneExpanded && tasks.length > DONE_COLLAPSE_THRESHOLD
      ? tasks.slice(-DONE_DEFAULT_VISIBLE)
      : tasks
  const hiddenCount = tasks.length - visibleTasks.length

  const { setNodeRef } = useDroppable({ id: stage })

  // Border highlight when a drag is active over this column
  const dropBorderColor = isDragOver
    ? isValidDropTarget
      ? 'var(--t-accent, #6c5ce7)'
      : 'rgba(217,112,112,0.5)'
    : 'transparent'

  const dropBg = isDragOver && isValidDropTarget
    ? 'rgba(108,92,231,0.05)'
    : 'transparent'

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        opacity: columnOpacity(stage),
        borderRadius: 'var(--t-radius-md)',
        border: `1px solid ${dropBorderColor}`,
        background: dropBg,
        transition: 'border-color 100ms ease, background 100ms ease',
        padding: '2px',
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
            fontSize: '12px',
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
            fontSize: '12px',
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
          gap: cardGap,
          overflowY: 'auto',
          flex: 1,
        }}
      >
        {/* Expand button shown when done column has many tasks */}
        {isDone && hiddenCount > 0 && (
          <button
            onClick={() => setDoneExpanded(true)}
            style={{
              background: 'none',
              border: '1px solid var(--t-border, rgba(255,255,255,0.08))',
              borderRadius: 'var(--t-radius-sm)',
              color: 'var(--t-text-3)',
              fontSize: '12px',
              cursor: 'pointer',
              padding: '4px 6px',
              textAlign: 'center',
              flexShrink: 0,
            }}
          >
            Show all {tasks.length} (+{hiddenCount} older)
          </button>
        )}

        {visibleTasks.map((task) => {
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
              isWide={isWide}
            />
          )
        })}

        {/* Drop placeholder: shown at bottom of valid target column during drag */}
        {isDragOver && isValidDropTarget && (
          <div
            aria-hidden="true"
            style={{
              height: '36px',
              borderRadius: 'var(--t-radius-md)',
              border: '1px dashed var(--t-accent, #6c5ce7)',
              opacity: 0.5,
              flexShrink: 0,
            }}
          />
        )}

        {/* Tooltip for invalid drop target */}
        {isDragOver && !isValidDropTarget && (
          <div
            aria-hidden="true"
            style={{
              padding: '4px 8px',
              borderRadius: 'var(--t-radius-sm)',
              background: 'rgba(217,112,112,0.12)',
              border: '1px solid rgba(217,112,112,0.3)',
              fontSize: '11px',
              color: '#d97070',
              textAlign: 'center',
              flexShrink: 0,
            }}
          >
            Pipeline controls this transition
          </div>
        )}
      </div>
    </div>
  )
}
