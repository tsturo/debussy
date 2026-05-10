import { useEffect, useRef, useState } from 'react'
import { ConductorMessage } from '../../shared/types'
import { useAppStore } from '../store/app-store'

// ── Types ────────────────────────────────────────────────────────────────────

type TabKey = 'watcher' | 'agents'

interface ConductorProps {
  messages: ConductorMessage[]
  isVisible: boolean
  onSend: (message: string) => void
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Split an AI message into text segments and command-block lines.
 * Lines beginning with "▸" are rendered as command blocks.
 */
function parseMessageContent(content: string): Array<{ type: 'text' | 'cmd'; value: string }> {
  const segments: Array<{ type: 'text' | 'cmd'; value: string }> = []
  let textBuffer: string[] = []

  for (const line of content.split('\n')) {
    if (line.startsWith('▸ ')) {
      if (textBuffer.length > 0) {
        segments.push({ type: 'text', value: textBuffer.join('\n') })
        textBuffer = []
      }
      segments.push({ type: 'cmd', value: line })
    } else {
      textBuffer.push(line)
    }
  }

  if (textBuffer.length > 0) {
    segments.push({ type: 'text', value: textBuffer.join('\n') })
  }

  return segments
}

// ── Sub-components ───────────────────────────────────────────────────────────

function CommandBlock({ text }: { text: string }) {
  return (
    <div
      style={{
        background: 'rgba(108, 92, 231, 0.08)',
        borderRadius: 9,
        padding: '4px 8px',
        marginTop: 4,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 10,
        color: 'var(--t-purple)',
        whiteSpace: 'pre',
      }}
    >
      {text}
    </div>
  )
}

function UserBubble({ message }: { message: ConductorMessage }) {
  return (
    <div
      style={{
        maxWidth: '85%',
        alignSelf: 'flex-end',
        background: 'rgba(108, 92, 231, 0.12)',
        borderRadius: '14px 14px 4px 14px',
        padding: '7px 10px',
        fontSize: 11,
        color: 'var(--t-text)',
        lineHeight: 1.5,
        wordBreak: 'break-word',
      }}
    >
      {message.content}
    </div>
  )
}

function AssistantBubble({ message }: { message: ConductorMessage }) {
  const segments = parseMessageContent(message.content)

  return (
    <div
      style={{
        maxWidth: '85%',
        alignSelf: 'flex-start',
        background: 'var(--t-bg)',
        border: '1px solid var(--t-border)',
        borderRadius: '14px 14px 14px 4px',
        padding: '7px 10px',
        fontSize: 11,
        color: 'var(--t-text-2)',
        lineHeight: 1.5,
        wordBreak: 'break-word',
      }}
    >
      {segments.map((seg, i) =>
        seg.type === 'cmd' ? (
          <CommandBlock key={i} text={seg.value} />
        ) : (
          <span key={i} style={{ whiteSpace: 'pre-wrap' }}>
            {seg.value}
          </span>
        )
      )}
    </div>
  )
}

/** Animated pulsing dots shown while the conductor is streaming a response. */
function StreamingIndicator({ content }: { content: string }) {
  return (
    <div
      style={{
        maxWidth: '85%',
        alignSelf: 'flex-start',
        background: 'var(--t-bg)',
        border: '1px solid var(--t-border)',
        borderRadius: '14px 14px 14px 4px',
        padding: '7px 10px',
        fontSize: 11,
        color: 'var(--t-text-2)',
        lineHeight: 1.5,
        wordBreak: 'break-word',
      }}
    >
      {content ? (
        <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
      ) : (
        <span style={{ display: 'flex', gap: 3, alignItems: 'center', height: 16 }}>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                background: 'var(--t-text-3)',
                display: 'inline-block',
                animation: `conductor-dot 1.2s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </span>
      )}
    </div>
  )
}

// ── Conductor ────────────────────────────────────────────────────────────────

export function Conductor({ messages, isVisible, onSend }: ConductorProps) {
  const [inputValue, setInputValue] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('watcher')
  const [streamingContent, setStreamingContent] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)

  const isStreaming = useAppStore((s) => s.conductorStreaming)
  const setConductorStreaming = useAppStore((s) => s.setConductorStreaming)
  const addConductorMessage = useAppStore((s) => s.addConductorMessage)
  const clearConductorMessages = useAppStore((s) => s.clearConductorMessages)

  // ── IPC listeners ──────────────────────────────────────────────────────────

  useEffect(() => {
    window.debussy.conductor.onChunk((chunk) => {
      setStreamingContent((prev) => prev + chunk)
    })

    window.debussy.conductor.onDone(() => {
      setStreamingContent((prev) => {
        if (prev) {
          addConductorMessage({
            id: `cm-ai-${Date.now()}`,
            role: 'assistant',
            content: prev,
            timestamp: Date.now(),
          })
        }
        return ''
      })
      setConductorStreaming(false)
    })

    return () => {
      window.debussy.conductor.removeListeners()
    }
  }, [addConductorMessage, setConductorStreaming])

  // Auto-scroll to bottom when messages or streaming content change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  if (!isVisible) return null

  function handleSend() {
    const trimmed = inputValue.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setInputValue('')
    setStreamingContent('')
  }

  function handleCancel() {
    window.debussy.conductor.cancel()
    setStreamingContent('')
    setConductorStreaming(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  async function handleNewSession() {
    window.debussy.conductor.cancel()
    setStreamingContent('')
    setConductorStreaming(false)
    clearConductorMessages()
    await window.debussy.conductor.newSession()
  }

  return (
    <div
      style={{
        width: 320,
        flexShrink: 0,
        background: 'var(--t-surface)',
        borderLeft: '1px solid var(--t-border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 52,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 14px',
          borderBottom: '1px solid var(--t-border)',
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--t-text)',
            letterSpacing: '-0.01em',
          }}
        >
          Conductor
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* New Session button */}
          <button
            onClick={handleNewSession}
            aria-label="New session"
            title="New Session"
            style={{
              width: 26,
              height: 26,
              flexShrink: 0,
              background: 'transparent',
              border: '1px solid var(--t-border)',
              borderRadius: 8,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--t-text-3)',
              transition: 'color var(--t-dur-fast), border-color var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--t-text)'
              e.currentTarget.style.borderColor = 'var(--t-text-3)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--t-text-3)'
              e.currentTarget.style.borderColor = 'var(--t-border)'
            }}
          >
            {/* Compose / new-chat icon */}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path
                d="M6 1H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V6"
                stroke="currentColor"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M9 1l2 2-4 4H5V5l4-4z"
                stroke="currentColor"
                strokeWidth="1.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {/* Segmented toggle */}
          <div
            style={{
              display: 'flex',
              background: 'var(--t-surface)',
              border: '1px solid var(--t-border)',
              borderRadius: 11,
              overflow: 'hidden',
            }}
          >
            {(['watcher', 'agents'] as TabKey[]).map((tab, idx) => {
              const isActive = activeTab === tab
              const label = tab === 'watcher' ? 'Watcher' : 'Agents'
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    background: isActive ? 'var(--t-bg)' : 'transparent',
                    border: 'none',
                    borderRadius:
                      idx === 0 ? '9px 0 0 9px' : '0 9px 9px 0',
                    padding: '4px 9px',
                    fontSize: 9,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
                    cursor: 'pointer',
                    transition: 'background var(--t-dur-fast), color var(--t-dur-fast)',
                    lineHeight: 1.4,
                    fontFamily: 'inherit',
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '10px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <UserBubble key={msg.id} message={msg} />
          ) : (
            <AssistantBubble key={msg.id} message={msg} />
          )
        )}
        {isStreaming && <StreamingIndicator content={streamingContent} />}
        <div ref={chatEndRef} />
      </div>

      {/* Input bar */}
      <div
        style={{
          flexShrink: 0,
          borderTop: '1px solid var(--t-border)',
          padding: '10px 12px',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}
      >
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Talk to conductor..."
          disabled={isStreaming}
          style={{
            flex: 1,
            background: 'var(--t-bg)',
            border: '1px solid var(--t-border)',
            borderRadius: 12,
            padding: '6px 10px',
            fontSize: 11,
            color: 'var(--t-text)',
            outline: 'none',
            fontFamily: 'inherit',
            minWidth: 0,
            opacity: isStreaming ? 0.5 : 1,
          }}
        />

        {/* Cancel button — only visible while streaming */}
        {isStreaming ? (
          <button
            onClick={handleCancel}
            aria-label="Cancel response"
            title="Cancel"
            style={{
              width: 32,
              height: 32,
              flexShrink: 0,
              background: 'var(--t-surface)',
              border: '1px solid var(--t-border)',
              borderRadius: 9,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--t-text-2)',
              transition: 'opacity var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            {/* X icon */}
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path
                d="M1 1l8 8M9 1L1 9"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        ) : (
          <button
            onClick={handleSend}
            aria-label="Send message"
            style={{
              width: 32,
              height: 32,
              flexShrink: 0,
              background: 'var(--t-gradient)',
              border: 'none',
              borderRadius: 9,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              transition: 'opacity var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            {/* Arrow icon */}
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M2 7h10M8 3l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>

      <style>{`
        @keyframes conductor-dot {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40%            { opacity: 1;   transform: scale(1); }
        }
      `}</style>
    </div>
  )
}

export default Conductor
