import React, { useState, useRef } from 'react'
import type { Task, LogEntry } from '../../shared/types'
import { TimelineColumn } from './TimelineColumn'
import { PencilIcon } from './icons'
import { useAppStore } from '../store/app-store'

// ── Props ─────────────────────────────────────────────────────────────────────

export interface TaskDetailBodyProps {
  task: Task
  logEntries: LogEntry[]
  agentName: string | null
  onComment: (message: string) => void
}

// ── Constants ─────────────────────────────────────────────────────────────────

// Regex: matches path-like tokens that contain at least one slash and a file
// extension, e.g. "src/debussy/cli.py" or "desktop/src/renderer/App.tsx".
const FILE_PATH_RE = /([\w.-]+(?:\/[\w.-]+)+\.\w{1,10})/g

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Render a description string with file-path tokens wrapped in clickable
 * purple spans. Returns an array of React nodes.
 */
function renderDescription(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const matches = Array.from(text.matchAll(FILE_PATH_RE))

  if (matches.length === 0) return [text]

  let lastIndex = 0
  for (const match of matches) {
    const start = match.index ?? 0
    if (start > lastIndex) {
      parts.push(text.slice(lastIndex, start))
    }
    const path = match[0]
    parts.push(
      <span
        key={start}
        style={{
          color: 'var(--t-purple)',
          cursor: 'pointer',
          textDecoration: 'none',
        }}
        onMouseEnter={e => {
          ;(e.currentTarget as HTMLElement).style.textDecoration = 'underline'
        }}
        onMouseLeave={e => {
          ;(e.currentTarget as HTMLElement).style.textDecoration = 'none'
        }}
        onClick={() => {
          // Future: open file in editor. No-op for now.
        }}
        title={path}
      >
        {path}
      </span>,
    )
    lastIndex = start + path.length
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts
}

// ── Left column: Description ──────────────────────────────────────────────────

interface DescriptionColumnProps {
  task: Task
}

function DescriptionColumn({ task }: DescriptionColumnProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const fetchAll = useAppStore((s) => s.fetchAll)

  const isDone = task.stage === 'done'
  const descriptionNodes = renderDescription(task.description)

  function startEditing() {
    setEditText(task.description)
    setSaveError(null)
    setIsEditing(true)
  }

  function cancelEditing() {
    setIsEditing(false)
    setEditText('')
    setSaveError(null)
  }

  async function saveDescription() {
    if (saving) return
    setSaving(true)
    setSaveError(null)
    try {
      const result = await window.debussy.tasks.update(task.id, { description: editText })
      if (result.success) {
        setIsEditing(false)
        setEditText('')
        await fetchAll()
      } else {
        setSaveError(result.error ?? 'Save failed')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'auto',
        padding: '12px 14px',
      }}
    >
      {/* Header row: DESCRIPTION label + optional pencil button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.10em',
            textTransform: 'uppercase',
            color: 'var(--t-text-3)',
          }}
        >
          Description
        </span>

        {!isDone && !isEditing && (
          <button
            onClick={startEditing}
            title="Edit description"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 2,
              borderRadius: 4,
              color: 'var(--t-text-3)',
              opacity: 0.7,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '0.7' }}
          >
            <PencilIcon />
          </button>
        )}
      </div>

      {isEditing ? (
        /* Edit mode */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <textarea
            value={editText}
            onChange={e => setEditText(e.target.value)}
            style={{
              width: '100%',
              minHeight: 120,
              background: 'var(--t-bg)',
              border: '1px solid var(--t-border)',
              borderRadius: 6,
              fontSize: 13,
              color: 'var(--t-text)',
              padding: '6px 8px',
              outline: 'none',
              resize: 'vertical',
              lineHeight: 1.6,
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
            autoFocus
          />
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              onClick={saveDescription}
              disabled={saving}
              style={{
                padding: '4px 10px',
                fontSize: 12,
                fontWeight: 600,
                background: 'var(--t-purple)',
                color: '#fff',
                border: 'none',
                borderRadius: 5,
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.6 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={cancelEditing}
              disabled={saving}
              style={{
                padding: '4px 10px',
                fontSize: 12,
                fontWeight: 600,
                background: 'none',
                color: 'var(--t-text-2)',
                border: '1px solid var(--t-border)',
                borderRadius: 5,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            {saveError && (
              <span style={{ fontSize: 11, color: 'var(--t-red, #e55)', marginLeft: 4 }}>
                {saveError}
              </span>
            )}
          </div>
        </div>
      ) : (
        /* Read mode */
        <div
          style={{
            fontSize: 13,
            color: 'var(--t-text-2)',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            flexShrink: 0,
          }}
        >
          {descriptionNodes}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TaskDetailBody({ task, logEntries, agentName, onComment }: TaskDetailBodyProps) {
  const [commentInput, setCommentInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && commentInput.trim() !== '') {
      onComment(commentInput.trim())
      setCommentInput('')
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* Two-column body */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        {/* Left: Description — key resets edit state when the selected task changes */}
        <DescriptionColumn key={task.id} task={task} />

        {/* Vertical divider */}
        <div
          style={{
            width: 1,
            backgroundColor: 'var(--t-border)',
            opacity: 0.6,
            flexShrink: 0,
            alignSelf: 'stretch',
          }}
        />

        {/* Right: Timeline — receives all entries; comments render inline */}
        <TimelineColumn timelineEntries={logEntries} agentName={agentName} />
      </div>

      {/* Comment input row */}
      <div
        style={{
          borderTop: '1px solid var(--t-border)',
          padding: '8px 14px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={commentInput}
          onChange={e => setCommentInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a comment..."
          style={{
            flex: 1,
            background: 'var(--t-bg)',
            border: '1px solid var(--t-border)',
            borderRadius: 9,
            fontSize: 13,
            color: 'var(--t-text)',
            padding: '5px 10px',
            outline: 'none',
          }}
        />
      </div>
    </div>
  )
}

export default TaskDetailBody
