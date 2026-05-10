import React, { useState, useRef } from 'react'
import type { Task, LogEntry } from '../../shared/types'

// ── Props ─────────────────────────────────────────────────────────────────────

export interface TaskDetailBodyProps {
  task: Task
  logEntries: LogEntry[]
  onComment: (message: string) => void
}

// ── Constants ─────────────────────────────────────────────────────────────────

// Keywords that can appear in log messages, mapped to their display color.
const ACTION_COLORS: Record<string, string> = {
  advanced: 'var(--t-purple)',
  claimed:  '#d4a843',
  released: 'var(--t-teal)',
  rejected: '#d97070',
  blocked:  '#d97070',
}

// Regex: matches path-like tokens that contain at least one slash and a file
// extension, e.g. "src/debussy/cli.py" or "desktop/src/renderer/App.tsx".
const FILE_PATH_RE = /([\w.-]+(?:\/[\w.-]+)+\.\w{1,10})/g

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Format an ISO timestamp to a short time string, e.g. "14:03:07". */
function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  } catch {
    return iso
  }
}

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
 * Return the first known action keyword found in a log message, or null.
 * The message is lowercased before searching.
 */
function extractAction(message: string): string | null {
  const lower = message.toLowerCase()
  for (const action of Object.keys(ACTION_COLORS)) {
    if (lower.includes(action)) return action
  }
  return null
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

// ── Sub-components ────────────────────────────────────────────────────────────

interface SectionLabelProps {
  children: React.ReactNode
}

function SectionLabel({ children }: SectionLabelProps) {
  return (
    <div
      style={{
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: '0.10em',
        textTransform: 'uppercase',
        color: 'var(--t-text-3)',
        marginBottom: 8,
        flexShrink: 0,
      }}
    >
      {children}
    </div>
  )
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
          fontSize: 11,
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
                  fontSize: 10,
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
                  fontSize: 11,
                  color: 'var(--t-text-2)',
                  lineHeight: 1.5,
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

// ── Right column: Timeline ────────────────────────────────────────────────────

interface TimelineColumnProps {
  timelineEntries: LogEntry[]
}

function TimelineColumn({ timelineEntries }: TimelineColumnProps) {
  const [showAgentOutput, setShowAgentOutput] = useState(false)

  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        padding: '12px 14px',
      }}
    >
      {/* Label row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 8,
          flexShrink: 0,
        }}
      >
        <SectionLabel>
          {showAgentOutput ? 'Agent Output' : 'Timeline'}
        </SectionLabel>

        {/* Toggle pill */}
        <button
          onClick={() => setShowAgentOutput(v => !v)}
          style={{
            fontSize: 9,
            color: 'var(--t-purple)',
            background: 'rgba(108, 92, 231, 0.10)',
            border: 'none',
            borderRadius: 100,
            padding: '2px 8px',
            cursor: 'pointer',
            marginBottom: 8,
            flexShrink: 0,
            lineHeight: 1.6,
            letterSpacing: '0.02em',
          }}
        >
          {showAgentOutput ? '← Timeline' : 'Agent Output →'}
        </button>
      </div>

      {/* Content area */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {showAgentOutput ? (
          // Agent output placeholder
          <div
            style={{
              fontFamily: '"SF Mono", "Fira Mono", "Menlo", monospace',
              fontSize: 10,
              lineHeight: 1.9,
              color: 'var(--t-text-3)',
              fontStyle: 'italic',
            }}
          >
            Agent output streaming not yet connected
          </div>
        ) : (
          // Timeline log
          <div
            style={{
              fontFamily: '"SF Mono", "Fira Mono", "Menlo", monospace',
              fontSize: 10,
              lineHeight: 1.9,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {timelineEntries.length === 0 ? (
              <span style={{ color: 'var(--t-text-3)', fontStyle: 'italic' }}>
                No events yet
              </span>
            ) : (
              timelineEntries.map(entry => {
                const action = extractAction(entry.message)
                const actionColor = action ? ACTION_COLORS[action] : 'var(--t-text-2)'

                // Split message around the action keyword for colored rendering.
                let beforeAction = entry.message
                let actionWord = ''
                let afterAction = ''

                if (action) {
                  const idx = entry.message.toLowerCase().indexOf(action)
                  if (idx !== -1) {
                    beforeAction = entry.message.slice(0, idx)
                    actionWord = entry.message.slice(idx, idx + action.length)
                    afterAction = entry.message.slice(idx + action.length)
                  }
                }

                return (
                  <div
                    key={entry.id}
                    style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}
                  >
                    {/* Timestamp */}
                    <span
                      style={{
                        color: 'var(--t-text-3)',
                        opacity: 0.6,
                        flexShrink: 0,
                        fontSize: 9,
                      }}
                    >
                      {formatTime(entry.timestamp)}
                    </span>

                    {/* Event line */}
                    <span style={{ color: 'var(--t-text-2)', minWidth: 0, wordBreak: 'break-word' }}>
                      <span style={{ color: actionColor }}>▸</span>{' '}
                      {action ? (
                        <>
                          {beforeAction}
                          <span style={{ color: actionColor, fontWeight: 600 }}>
                            {actionWord}
                          </span>
                          {afterAction}
                        </>
                      ) : (
                        entry.message
                      )}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function TaskDetailBody({ task, logEntries, onComment }: TaskDetailBodyProps) {
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
        <TimelineColumn timelineEntries={timelineEntries} />
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
            fontSize: 11,
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
