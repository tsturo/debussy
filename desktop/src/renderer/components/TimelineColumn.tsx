import React, { useState, useRef, useEffect, useCallback } from 'react'
import type { LogEntry } from '../../shared/types'

// ── Constants ─────────────────────────────────────────────────────────────────

/** Maximum number of agent log lines held in memory at once (ring buffer). */
export const MAX_LOG_LINES = 500

// Keywords that can appear in log messages, mapped to their display color.
const ACTION_COLORS: Record<string, string> = {
  advanced: 'var(--t-purple)',
  claimed:  '#d4a843',
  released: 'var(--t-teal)',
  rejected: '#d97070',
  blocked:  '#d97070',
}

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

// ── Sub-components ────────────────────────────────────────────────────────────

interface SectionLabelProps {
  children: React.ReactNode
}

export function SectionLabel({ children }: SectionLabelProps) {
  return (
    <div
      style={{
        fontSize: 11,
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

// ── TimelineColumn ────────────────────────────────────────────────────────────

export interface TimelineColumnProps {
  timelineEntries: LogEntry[]
  agentName: string | null
}

export function TimelineColumn({ timelineEntries, agentName }: TimelineColumnProps) {
  const [showAgentOutput, setShowAgentOutput] = useState(false)
  const [logLines, setLogLines] = useState<string[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)

  // Append incoming log line, capping the buffer at MAX_LOG_LINES.
  const handleLogLine = useCallback(
    (data: { agent: string; line: string }) => {
      if (data.agent !== agentName) return
      setLogLines(prev => {
        const next = [...prev, data.line]
        return next.length > MAX_LOG_LINES ? next.slice(next.length - MAX_LOG_LINES) : next
      })
    },
    [agentName],
  )

  // Start/stop streaming when the Agent Output tab is toggled or agentName changes.
  useEffect(() => {
    if (!showAgentOutput || !agentName) return

    setLogLines([])
    window.debussy.agents.onLogLine(handleLogLine)
    window.debussy.agents.startLog(agentName)

    return () => {
      window.debussy.agents.stopLog(agentName)
      window.debussy.agents.removeLogListener()
    }
  }, [showAgentOutput, agentName, handleLogLine])

  // Auto-scroll to bottom whenever new lines arrive.
  useEffect(() => {
    if (showAgentOutput) {
      logEndRef.current?.scrollIntoView({ behavior: 'auto' })
    }
  }, [logLines, showAgentOutput])

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
            fontSize: 11,
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
          // Agent output
          <div
            style={{
              fontFamily: '"SF Mono", "Fira Mono", "Menlo", monospace',
              fontSize: 11,
              lineHeight: 1.7,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {!agentName ? (
              <span style={{ color: 'var(--t-text-3)', fontStyle: 'italic', fontSize: 11 }}>
                No agent currently active for this task
              </span>
            ) : logLines.length === 0 ? (
              <span style={{ color: 'var(--t-text-3)', fontStyle: 'italic', fontSize: 11 }}>
                Waiting for output…
              </span>
            ) : (
              logLines.map((line, i) => (
                <span
                  key={i}
                  style={{ color: 'var(--t-text-2)', wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}
                >
                  {line}
                </span>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        ) : (
          // Timeline log
          <div
            style={{
              fontFamily: '"SF Mono", "Fira Mono", "Menlo", monospace',
              fontSize: 12,
              lineHeight: 1.8,
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
                        fontSize: 11,
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

export default TimelineColumn
