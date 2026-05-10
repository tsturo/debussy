import { useState } from 'react'
import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { formatElapsed } from '../lib/format'

export interface KanbanCardProps {
  task: Task
  /** Agent currently working this task, sourced from watcher state. */
  agent: { name: string; stage: Stage; startedAt?: number } | null
  isSelected: boolean
  onClick: () => void
}

export function KanbanCard({ task, agent, isSelected, onClick }: KanbanCardProps) {
  const [isHovered, setIsHovered] = useState(false)

  const stageColor = STAGE_COLORS[task.stage].color

  // Compose box-shadow: hover elevation + selection ring
  const shadows: string[] = []
  if (isHovered) shadows.push('var(--t-shadow-card-hover)')
  if (isSelected) shadows.push(`0 0 0 1px ${stageColor}66`)
  const boxShadow = shadows.length > 0 ? shadows.join(', ') : 'none'

  const showBottomRow = task.status === 'blocked' || agent !== null

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        backgroundColor: 'var(--t-card-bg)',
        borderRadius: 'var(--t-radius-md)',
        padding: '10px 12px',
        borderLeft: `${isSelected ? 3 : 2}px solid ${stageColor}`,
        cursor: 'pointer',
        transform: isHovered ? 'translateY(-1px)' : 'none',
        boxShadow,
        transition: 'transform 150ms var(--t-ease), box-shadow 150ms var(--t-ease)',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        userSelect: 'none',
      }}
    >
      {/* Top row: task ID + rejection badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          fontSize: '10px',
          fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
          color: 'var(--t-text-3)',
          lineHeight: 1,
        }}>
          {task.id}
        </span>

        {task.rejection_count > 0 && (
          <span
            title={`Rejected ${task.rejection_count} time${task.rejection_count !== 1 ? 's' : ''}`}
            style={{
              width: '16px',
              height: '16px',
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
      </div>

      {/* Title: 2-line clamp */}
      <p style={{
        fontSize: '12px',
        fontWeight: 500,
        color: 'var(--t-text)',
        margin: 0,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        lineHeight: 1.4,
      }}>
        {task.title}
      </p>

      {/* Bottom row: blocked indicator OR agent avatar + elapsed time */}
      {showBottomRow && (
        task.status === 'blocked' ? (
          <div style={{ fontSize: '10px', color: 'var(--t-error)', lineHeight: 1 }}>
            ⊘ blocked
          </div>
        ) : agent && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            {/* Mini avatar with stage-colored ring */}
            <div
              aria-hidden="true"
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: `${stageColor}22`,
                border: `1.5px solid ${stageColor}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '8px',
                fontWeight: 700,
                color: stageColor,
                flexShrink: 0,
                lineHeight: 1,
              }}
            >
              {agent.name.charAt(0).toUpperCase()}
            </div>

            {/* Elapsed time */}
            {agent.startedAt !== undefined && (
              <span style={{ fontSize: '10px', color: 'var(--t-text-3)', lineHeight: 1 }}>
                {formatElapsed(agent.startedAt)}
              </span>
            )}
          </div>
        )
      )}
    </div>
  )
}
