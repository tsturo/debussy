import type { Stage } from '../../shared/types'
import { STAGE_LABELS } from '../lib/move-validation'

export interface DragConfirmDialogProps {
  taskId: string
  taskTitle: string
  fromStage: Stage
  toStage: Stage
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Confirmation dialog shown before executing a board drag-and-drop move.
 * Always shown — moves are never auto-applied on drop.
 */
export function DragConfirmDialog({
  taskId,
  taskTitle,
  fromStage,
  toStage,
  onConfirm,
  onCancel,
}: DragConfirmDialogProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onCancel}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 200,
          background: 'rgba(0,0,0,0.45)',
        }}
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Confirm task move"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 201,
          background: 'var(--t-surface)',
          border: '1px solid var(--t-border)',
          borderRadius: 'var(--t-radius-lg)',
          padding: '20px 24px',
          minWidth: '320px',
          maxWidth: '420px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.32)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {/* Title */}
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--t-text)' }}>
          Move task?
        </div>

        {/* Body */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div
            style={{
              fontSize: '12px',
              color: 'var(--t-text-2)',
              display: 'flex',
              alignItems: 'baseline',
              gap: '4px',
              flexWrap: 'wrap',
            }}
          >
            <span
              style={{
                fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
                color: 'var(--t-text-3)',
                fontSize: '11px',
              }}
            >
              {taskId}
            </span>
            <span style={{ fontWeight: 500, color: 'var(--t-text)', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {taskTitle}
            </span>
          </div>

          <div
            style={{
              fontSize: '12px',
              color: 'var(--t-text-3)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span style={{ padding: '2px 6px', background: 'var(--t-bg)', borderRadius: 4, fontSize: '12px' }}>
              {STAGE_LABELS[fromStage]}
            </span>
            <span aria-hidden="true">→</span>
            <span style={{ padding: '2px 6px', background: 'var(--t-bg)', borderRadius: 4, fontSize: '12px', color: 'var(--t-accent)' }}>
              {STAGE_LABELS[toStage]}
            </span>
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '6px 14px',
              fontSize: '12px',
              borderRadius: 'var(--t-radius-sm)',
              border: '1px solid var(--t-border)',
              background: 'transparent',
              color: 'var(--t-text-2)',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            autoFocus
            onClick={onConfirm}
            style={{
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: 'var(--t-radius-sm)',
              border: 'none',
              background: 'var(--t-accent)',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Confirm
          </button>
        </div>
      </div>
    </>
  )
}
