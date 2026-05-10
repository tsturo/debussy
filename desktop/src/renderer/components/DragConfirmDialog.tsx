import type { Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'

export interface DragConfirmDialogProps {
  taskId: string
  taskTitle: string
  fromStage: Stage
  toStage: Stage
  onConfirm: () => Promise<void>
  onCancel: () => void
}

export function DragConfirmDialog({
  taskId,
  taskTitle,
  fromStage,
  toStage,
  onConfirm,
  onCancel,
}: DragConfirmDialogProps) {
  const fromLabel = STAGE_COLORS[fromStage].label
  const toLabel = STAGE_COLORS[toStage].label
  const toColor = STAGE_COLORS[toStage].color

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Move ${taskId} to ${toLabel}`}
      onClick={onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.55)',
        zIndex: 9999,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: 'var(--t-card-bg)',
          borderRadius: 'var(--t-radius-md)',
          padding: '20px 24px',
          minWidth: '300px',
          maxWidth: '380px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          border: `1px solid ${toColor}33`,
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span
            style={{
              fontSize: '11px',
              fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
              color: 'var(--t-text-3)',
            }}
          >
            {taskId}
          </span>
          <p
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--t-text)',
              margin: 0,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: 1.4,
            }}
          >
            {taskTitle}
          </p>
        </div>

        {/* Transition row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 12px',
            backgroundColor: 'rgba(255,255,255,0.04)',
            borderRadius: 'var(--t-radius-sm)',
          }}
        >
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: STAGE_COLORS[fromStage].color,
              letterSpacing: '0.04em',
            }}
          >
            {fromLabel}
          </span>
          <span style={{ color: 'var(--t-text-3)', fontSize: '12px' }}>→</span>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: toColor,
              letterSpacing: '0.04em',
            }}
          >
            {toLabel}
          </span>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '7px 14px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: 'var(--t-radius-sm)',
              border: '1px solid var(--t-border)',
              backgroundColor: 'transparent',
              color: 'var(--t-text-2)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={async () => { await onConfirm() }}
            style={{
              padding: '7px 14px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: 'var(--t-radius-sm)',
              border: `1px solid ${toColor}`,
              backgroundColor: `${toColor}22`,
              color: toColor,
              cursor: 'pointer',
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
