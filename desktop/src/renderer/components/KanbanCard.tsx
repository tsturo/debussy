import { useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { formatElapsed } from '../lib/format'

export interface KanbanCardProps {
  task: Task
  /** Agent currently working this task, sourced from watcher state. */
  agent: { name: string; stage: Stage; startedAt?: number } | null
  isSelected: boolean
  onClick: () => void
  /** Whether this card can be dragged (false for done-stage cards). */
  draggable?: boolean
}

export function KanbanCard({ task, agent, isSelected, onClick, draggable = true }: KanbanCardProps) {
  const [isHovered, setIsHovered] = useState(false)

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    disabled: !draggable,
    data: {
      taskId: task.id,
      taskTitle: task.title,
      fromStage: task.stage,
      isBlocked: task.status === 'blocked',
    },
  })

  const stageColor = STAGE_COLORS[task.stage].color

  // Compose box-shadow: hover elevation + selection ring
  const shadows: string[] = []
  if (isDragging) {
    shadows.push('0 8px 24px rgba(0,0,0,0.5)')
  } else if (isHovered) {
    shadows.push('var(--t-shadow-card-hover)')
  }
  if (isSelected) shadows.push(`0 0 0 1px ${stageColor}66`)
  const boxShadow = shadows.length > 0 ? shadows.join(', ') : 'none'

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        backgroundColor: 'var(--t-card-bg)',
        borderRadius: 'var(--t-radius-md)',
        padding: '8px',
        borderLeft: `${isSelected ? 3 : 2}px solid ${stageColor}`,
        cursor: draggable ? (isDragging ? 'grabbing' : 'grab') : 'default',
        transform: isDragging ? 'scale(1.02)' : isHovered ? 'translateY(-1px)' : 'none',
        boxShadow,
        opacity: isDragging ? 0.45 : 1,
        transition: isDragging ? 'none' : 'transform 150ms var(--t-ease), box-shadow 150ms var(--t-ease)',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        userSelect: 'none',
        minHeight: '36px',
        touchAction: 'none',
      }}
    >
      {/* ID · title on one line */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'baseline',
          gap: '4px',
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        <span
          style={{
            fontSize: '10px',
            fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
            color: 'var(--t-text-3)',
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          {task.id}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--t-text-3)', lineHeight: 1, flexShrink: 0 }}>
          ·
        </span>
        <span
          style={{
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--t-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            lineHeight: 1.3,
          }}
        >
          {task.title}
        </span>
      </div>

      {/* Rejection count badge */}
      {task.rejection_count > 0 && (
        <span
          title={`Rejected ${task.rejection_count} time${task.rejection_count !== 1 ? 's' : ''}`}
          style={{
            width: '14px',
            height: '14px',
            borderRadius: '50%',
            backgroundColor: 'rgba(217,112,112,0.15)',
            color: '#d97070',
            fontSize: '8px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            lineHeight: 1,
          }}
        >
          {task.rejection_count}
        </span>
      )}

      {/* Blocked indicator */}
      {task.status === 'blocked' && (
        <span
          style={{ fontSize: '10px', color: 'var(--t-error)', lineHeight: 1, flexShrink: 0 }}
        >
          ⊘
        </span>
      )}

      {/* Agent avatar + elapsed time (right-aligned, inline) */}
      {task.status !== 'blocked' && agent !== null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
          <div
            aria-hidden="true"
            style={{
              width: '14px',
              height: '14px',
              borderRadius: '50%',
              backgroundColor: `${stageColor}22`,
              border: `1.5px solid ${stageColor}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '7px',
              fontWeight: 700,
              color: stageColor,
              flexShrink: 0,
              lineHeight: 1,
            }}
          >
            {agent.name.charAt(0).toUpperCase()}
          </div>
          {agent.startedAt !== undefined && (
            <span style={{ fontSize: '10px', color: 'var(--t-text-3)', lineHeight: 1 }}>
              {formatElapsed(agent.startedAt)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
