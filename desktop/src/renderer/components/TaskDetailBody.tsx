import React, { useState, useRef } from 'react'
import type { Task, LogEntry } from '../../shared/types'
import { TimelineColumn, SectionLabel } from './TimelineColumn'

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

/** Format an ISO timestamp to a readable comment header, e.g. "14:03 · 10 May". */
function formatCommentTime(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const day = d.getDate()
    const month = d.toLocaleString('en', { month: 'short' })
    return `${hh}:${mm} · ${day} ${month}`
  } catch {
    return iso
  }
}

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
  comments: LogEntry[]
}

function DescriptionColumn({ task, comments }: DescriptionColumnProps) {
  const descriptionNodes = renderDescription(task.description)

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
      <SectionLabel>Description</SectionLabel>

      {/* Description text */}
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
  const inputRef = useRef<HTMLInputElement>(null)

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
        <DescriptionColumn task={task} comments={comments} />

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

        {/* Right: Timeline */}
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
