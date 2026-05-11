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
  /** When true, the card renders as a static overlay clone (no drag/events). */
  isDragOverlay?: boolean
  /** When true, the title renders on up to two lines; when false, single line with ellipsis. */
  isWide?: boolean
}

export function KanbanCard({ task, agent, isSelected, onClick, isDragOverlay = false, isWide = true }: KanbanCardProps) {
  const [isHovered, setIsHovered] = useState(false)

  const isDone = task.stage === 'done'

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    data: { taskId: task.id, fromStage: task.stage, status: task.status },
    disabled: isDone || isDragOverlay,
  })

  const stageColor = STAGE_COLORS[task.stage].color

  // Compose box-shadow: hover elevation + selection ring + drag elevation
  const shadows: string[] = []
  if (isDragOverlay) {
    shadows.push('0 8px 24px rgba(0,0,0,0.35)', `0 0 0 1px ${stageColor}66`)
  } else {
    if (isHovered && !isDragging) shadows.push('var(--t-shadow-card-hover)')
    if (isSelected) shadows.push(`0 0 0 1px ${stageColor}66`)
  }
  const boxShadow = shadows.length > 0 ? shadows.join(', ') : 'none'

  const transform =
    isDragOverlay
      ? 'scale(1.02)'
      : isHovered && !isDragging
      ? 'translateY(-1px)'
      : 'none'

  return (
    <div
      ref={isDragOverlay ? undefined : setNodeRef}
      {...(isDragOverlay ? {} : listeners)}
      {...(isDragOverlay ? {} : attributes)}
      // Override aria-disabled set by dnd-kit when drag is disabled:
      // done-stage cards are still fully clickable (to open the detail panel),
      // so advertising them as disabled is misleading and breaks Playwright clicks.
      aria-disabled={undefined}
      role="button"
      data-task-id={task.id}
      tabIndex={isDone ? -1 : 0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        backgroundColor: 'var(--t-card-bg)',
        borderRadius: 'var(--t-radius-md)',
        padding: '8px',
        borderLeft: `${isSelected ? 3 : 2}px solid ${stageColor}`,
        cursor: isDone ? 'default' : isDragging ? 'grabbing' : 'grab',
        transform,
        boxShadow,
        transition: isDragOverlay
          ? 'none'
          : 'transform 150ms var(--t-ease), box-shadow 150ms var(--t-ease)',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        userSelect: 'none',
        minHeight: '36px',
        // Fade the card in its original slot while being dragged
        opacity: isDragging ? 0.4 : 1,
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
            fontSize: '11px',
            fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
            color: 'var(--t-text-3)',
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          {task.id}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--t-text-3)', lineHeight: 1, flexShrink: 0 }}>
          ·
        </span>
        <span
          style={
            isWide
              ? {
                  fontSize: '12px',
                  fontWeight: 500,
                  color: 'var(--t-text)',
                  overflow: 'hidden',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  lineHeight: 1.3,
                }
              : {
                  fontSize: '12px',
                  fontWeight: 500,
                  color: 'var(--t-text)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  lineHeight: 1.3,
                }
          }
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
            fontSize: '11px',
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
          style={{ fontSize: '11px', color: 'var(--t-error)', lineHeight: 1, flexShrink: 0 }}
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
              fontSize: '11px',
              fontWeight: 700,
              color: stageColor,
              flexShrink: 0,
              lineHeight: 1,
            }}
          >
            {agent.name.charAt(0).toUpperCase()}
          </div>
          {agent.startedAt !== undefined && (
            <span style={{ fontSize: '11px', color: 'var(--t-text-3)', lineHeight: 1 }}>
              {formatElapsed(agent.startedAt)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
