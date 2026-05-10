import React, { useState, useRef, useCallback, useEffect } from 'react'
import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'

/** Compact stage labels used in the status strip. */
const STRIP_STAGES: Array<[Stage, string]> = [
  ['development', 'dev'],
  ['reviewing', 'review'],
  ['merging', 'merge'],
  ['done', 'done'],
]

// ── Props ─────────────────────────────────────────────────────────────────────

export interface TaskDetailShellProps {
  task: Task | null
  agent: { name: string; stage: Stage } | null
  watcherRunning: boolean
  agentCount: number
  lastEvent: string       // e.g. "DBS-3 → reviewing"
  stageCounts: Partial<Record<Stage, number>>
  onClose: () => void
  onAdvance: () => void
  onBlock: () => void
  children: React.ReactNode
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatElapsed(isoTimestamp: string): string {
  const ms = Date.now() - new Date(isoTimestamp).getTime()
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const hours = Math.floor(minutes / 60)
  if (hours > 0) return `${hours}h ${minutes % 60}m`
  if (minutes > 0) return `${minutes}m`
  return `${totalSeconds}s`
}

// Approx 12% alpha as hex suffix on a #rrggbb color.
function withAlpha12(hex: string): string {
  return `${hex}1f`
}

// ── Collapsed strip ───────────────────────────────────────────────────────────

interface CollapsedStripProps {
  watcherRunning: boolean
  agentCount: number
  lastEvent: string
  stageCounts: Partial<Record<Stage, number>>
}

function CollapsedStrip({ watcherRunning, agentCount, lastEvent, stageCounts }: CollapsedStripProps) {
  const stageCountStr = STRIP_STAGES
    .filter(([stage]) => (stageCounts[stage] ?? 0) > 0)
    .map(([stage, label]) => `${stageCounts[stage]} ${label}`)
    .join(' · ')

  return (
    <div
      style={{
        height: 36,
        backgroundColor: 'var(--t-surface)',
        borderTop: '1px solid var(--t-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {/* Left: status dot + label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: watcherRunning ? 'var(--t-teal)' : 'var(--t-muted)',
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--t-text-2)', whiteSpace: 'nowrap' }}>
          {watcherRunning ? 'Watching' : 'Idle'}
        </span>
      </div>

      {/* Center: stage counts + agent count + last event */}
      <div
        style={{
          flex: 1,
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--t-text-3)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          padding: '0 12px',
        }}
      >
        {stageCountStr || `${agentCount} agent${agentCount !== 1 ? 's' : ''}`}
        {lastEvent ? ` · last: ${lastEvent}` : ''}
      </div>

      {/* Right: chevron-up icon (visual indicator — no task selected) */}
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          color: 'var(--t-text-3)',
          padding: 4,
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M2 8L6 4L10 8"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TaskDetailShell({
  task,
  agent,
  watcherRunning,
  agentCount,
  lastEvent,
  stageCounts,
  onClose,
  onAdvance,
  onBlock,
  children,
}: TaskDetailShellProps) {
  const [panelHeight, setPanelHeight] = useState(200)
  const [animateIn, setAnimateIn] = useState(false)
  const [elapsed, setElapsed] = useState('')
  const isDragging = useRef(false)
  const dragStartY = useRef(0)
  const dragStartHeight = useRef(0)

  // Slide-up animation: set animateIn to false on first render, true after one
  // frame so the CSS transition kicks in.
  const prevTaskRef = useRef<Task | null>(null)
  useEffect(() => {
    if (task !== null && prevTaskRef.current === null) {
      // Task was just selected — trigger entrance animation
      setAnimateIn(false)
      const raf = requestAnimationFrame(() => setAnimateIn(true))
      return () => cancelAnimationFrame(raf)
    }
    prevTaskRef.current = task
  }, [task])

  // Update elapsed every 10 s (from task.updated_at as a proxy for stage entry)
  useEffect(() => {
    if (!task) return
    const update = () => setElapsed(formatElapsed(task.updated_at))
    update()
    const id = setInterval(update, 10_000)
    return () => clearInterval(id)
  }, [task?.updated_at])

  // Drag-to-resize
  const handleDragMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true
      dragStartY.current = e.clientY
      dragStartHeight.current = panelHeight
    },
    [panelHeight],
  )

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!isDragging.current) return
      const delta = dragStartY.current - e.clientY
      const newHeight = dragStartHeight.current + delta
      const maxHeight = window.innerHeight * 0.7
      setPanelHeight(Math.max(120, Math.min(newHeight, maxHeight)))
    }
    function onMouseUp() {
      isDragging.current = false
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  // ── Collapsed strip ──────────────────────────────────────────────────────

  if (task === null) {
    return (
      <CollapsedStrip
        watcherRunning={watcherRunning}
        agentCount={agentCount}
        lastEvent={lastEvent}
        stageCounts={stageCounts}
      />
    )
  }

  // ── Expanded panel ───────────────────────────────────────────────────────

  const stageDisplay = STAGE_COLORS[task.stage]

  return (
    <div
      style={{
        height: panelHeight,
        minHeight: 120,
        backgroundColor: 'var(--t-surface)',
        borderTop: '1px solid var(--t-border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflow: 'hidden',
        // Slide-up entrance animation via CSS transition
        transform: animateIn ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}
    >
      {/* Drag handle */}
      <div
        onMouseDown={handleDragMouseDown}
        style={{
          height: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'row-resize',
          flexShrink: 0,
          userSelect: 'none',
        }}
      >
        <div
          style={{
            width: 32,
            height: 3,
            backgroundColor: 'var(--t-border)',
            borderRadius: 100,
          }}
        />
      </div>

      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '14px 16px',
          borderBottom: '1px solid var(--t-border)',
          flexShrink: 0,
          minWidth: 0,
        }}
      >
        {/* Task ID */}
        <span
          style={{
            fontSize: 12,
            fontFamily: 'monospace',
            color: 'var(--t-text-3)',
            flexShrink: 0,
          }}
        >
          {task.id}
        </span>

        {/* Stage badge */}
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: stageDisplay.color,
            backgroundColor: withAlpha12(stageDisplay.color),
            borderRadius: 100,
            padding: '2px 8px',
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          {stageDisplay.label}
        </span>

        {/* Title */}
        <span
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--t-text)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
        >
          {task.title}
        </span>

        {/* Flex spacer */}
        <div style={{ flex: 1 }} />

        {/* Agent badge */}
        {agent !== null && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--t-purple)',
              backgroundColor: 'rgba(108, 92, 231, 0.12)',
              borderRadius: 100,
              padding: '2px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: 5,
                height: 5,
                borderRadius: '50%',
                backgroundColor: 'var(--t-purple)',
              }}
            />
            {agent.name}
          </span>
        )}

        {/* Elapsed */}
        {elapsed !== '' && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--t-text-2)',
              backgroundColor: 'rgba(168, 176, 194, 0.10)',
              borderRadius: 100,
              padding: '2px 8px',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            {elapsed}
          </span>
        )}

        {/* Rejection badge (only if rejection_count > 0) */}
        {task.rejection_count > 0 && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--t-error)',
              backgroundColor: 'rgba(217, 112, 112, 0.12)',
              borderRadius: 100,
              padding: '2px 8px',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            {task.rejection_count}✕ rejected
          </span>
        )}

        {/* Block button */}
        <button
          onClick={onBlock}
          style={{
            fontSize: 12,
            color: 'var(--t-warn)',
            backgroundColor: 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderRadius: 9,
            padding: '4px 10px',
            cursor: 'pointer',
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          Block
        </button>

        {/* Advance button */}
        <button
          onClick={onAdvance}
          style={{
            fontSize: 12,
            color: '#ffffff',
            background: 'var(--t-gradient)',
            border: 'none',
            borderRadius: 9,
            padding: '4px 10px',
            cursor: 'pointer',
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          Advance
        </button>

        {/* Close button (24px hit target) */}
        <button
          onClick={onClose}
          aria-label="Close task detail"
          style={{
            width: 24,
            height: 24,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--t-text-3)',
            flexShrink: 0,
            borderRadius: 4,
            fontSize: 13,
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* Body slot */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {children}
      </div>
    </div>
  )
}

export default TaskDetailShell
