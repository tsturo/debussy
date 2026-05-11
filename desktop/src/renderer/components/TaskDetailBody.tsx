import React, { useState, useRef } from 'react'
import type { Task, LogEntry } from '../../shared/types'
import { TimelineColumn } from './TimelineColumn'

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

/** Format a comment timestamp as a short relative or absolute string. */
function formatCommentTime(timestamp: string): string {
  const date = new Date(timestamp)
  if (isNaN(date.getTime())) return timestamp
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ── Left column: Description ──────────────────────────────────────────────────

interface DescriptionColumnProps {
  task: Task
  comments: LogEntry[]
  onDescriptionSaved: (newDescription: string) => void
}

function DescriptionColumn({ task, comments, onDescriptionSaved }: DescriptionColumnProps) {
  const [editing, setEditing] = useState(false)
  const [draftText, setDraftText] = useState('')
  const [saving, setSaving] = useState(false)

  const isDone = task.stage === 'done'
  const descriptionNodes = renderDescription(task.description)

  function handleEditClick() {
    setDraftText(task.description)
    setEditing(true)
  }

  function handleCancel() {
    setEditing(false)
    setDraftText('')
  }

  async function handleSave() {
    if (saving) return
    setSaving(true)
    try {
      const result = await window.debussy.tasks.update(task.id, { description: draftText })
      if (result.success) {
        onDescriptionSaved(draftText)
        setEditing(false)
        setDraftText('')
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
      {/* Section label row with optional Edit button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.10em',
            textTransform: 'uppercase',
            color: 'var(--t-text-3)',
            flexShrink: 0,
          }}
        >
          Description
        </div>
        {!isDone && !editing && (
          <button
            onClick={handleEditClick}
            title="Edit description"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--t-text-3)',
              padding: '2px 4px',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              fontSize: 11,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'var(--t-purple)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'var(--t-text-3)' }}
          >
            {/* Pencil icon */}
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11.5 2.5a2.121 2.121 0 0 1 3 3L5 15H2v-3L11.5 2.5z"/>
            </svg>
            Edit
          </button>
        )}
      </div>

      {editing ? (
        /* Edit mode */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
          <textarea
            value={draftText}
            onChange={e => setDraftText(e.target.value)}
            style={{
              width: '100%',
              minHeight: 120,
              background: 'var(--t-bg)',
              border: '1px solid var(--t-border)',
              borderRadius: 6,
              fontSize: 13,
              color: 'var(--t-text-2)',
              lineHeight: 1.6,
              padding: '6px 8px',
              resize: 'vertical',
              outline: 'none',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
            autoFocus
          />
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                background: 'var(--t-purple)',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={handleCancel}
              disabled={saving}
              style={{
                background: 'none',
                border: '1px solid var(--t-border)',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                color: 'var(--t-text-2)',
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        /* Read mode: description text */
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

      {/* Inline comments */}
      {comments.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {comments.map(entry => (
            <div
              key={entry.id}
              style={{
                background: 'rgba(108, 92, 231, 0.06)',
                borderRadius: 9,
                borderLeft: '2px solid var(--t-purple)',
                padding: '8px 10px',
              }}
            >
              {/* Author + timestamp */}
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--t-text-3)',
                  marginBottom: 4,
                  display: 'flex',
                  gap: 6,
                  alignItems: 'baseline',
                }}
              >
                <span style={{ fontWeight: 600 }}>{entry.author}</span>
                <span>{formatCommentTime(entry.timestamp)}</span>
              </div>
              {/* Comment body */}
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--t-text-2)',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {entry.message}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TaskDetailBody({ task, logEntries, agentName, onComment }: TaskDetailBodyProps) {
  const [commentInput, setCommentInput] = useState('')
  const [localDescription, setLocalDescription] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Reset local description override whenever the selected task changes
  const prevTaskIdRef = useRef(task.id)
  if (prevTaskIdRef.current !== task.id) {
    prevTaskIdRef.current = task.id
    setLocalDescription(null)
  }

  const displayTask = localDescription !== null ? { ...task, description: localDescription } : task

  const comments = logEntries.filter(e => e.type === 'comment')
  const timelineEntries = logEntries.filter(
    e => e.type === 'transition' || e.type === 'assignment',
  )

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
        {/* Left: Description */}
        <DescriptionColumn task={displayTask} comments={comments} onDescriptionSaved={setLocalDescription} />

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

        {/* Right: Timeline — receives transition/assignment entries only; comments render inline */}
        <TimelineColumn timelineEntries={timelineEntries} agentName={agentName} />
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
