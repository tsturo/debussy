import { useEffect, useRef, useState } from 'react'
import { ConductorMessage } from '../../shared/types'

// ── Mock data ────────────────────────────────────────────────────────────────

export const DEFAULT_MESSAGES: ConductorMessage[] = [
  {
    id: '1',
    role: 'user',
    content: 'Create tasks for auth: user model, login endpoint, JWT middleware',
    timestamp: Date.now() - 5 * 60 * 1000,
  },
  {
    id: '2',
    role: 'assistant',
    content:
      "Created 3 tasks ready for development:\n• DBS-1: User model (Pydantic schema + DB migration)\n• DBS-2: Login endpoint (POST /auth/login, bcrypt)\n• DBS-6: JWT middleware (access + refresh tokens)\n▸ takt create \"User model\" -d \"...\"\n▸ takt create \"Login endpoint\" -d \"...\"\n▸ takt create \"JWT middleware\" -d \"...\"\n▸ takt advance DBS-1\n▸ takt advance DBS-2\n▸ takt advance DBS-6",
    timestamp: Date.now() - 4 * 60 * 1000,
  },
  {
    id: '3',
    role: 'user',
    content: 'DBS-6 keeps getting rejected — what\'s wrong?',
    timestamp: Date.now() - 2 * 60 * 1000,
  },
  {
    id: '4',
    role: 'assistant',
    content:
      "The reviewer flagged a token refresh race condition — two simultaneous refresh requests can both succeed and generate conflicting tokens. Fix: add a Redis lock around the refresh flow, or use a short-lived single-use refresh nonce.\n▸ takt log DBS-6\n▸ takt comment DBS-6 \"Add refresh lock before re-advancing\"",
    timestamp: Date.now() - 90 * 1000,
  },
  {
    id: '5',
    role: 'user',
    content: 'Got it. Can you check the board and tell me what\'s blocked?',
    timestamp: Date.now() - 30 * 1000,
  },
  {
    id: '6',
    role: 'assistant',
    content:
      'DBS-6 is blocked pending the refresh fix. Everything else looks healthy — DBS-1 is in reviewing, DBS-2 just merged. You\'re on track.\n▸ debussy board',
    timestamp: Date.now() - 15 * 1000,
  },
]

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

// ── Conductor ────────────────────────────────────────────────────────────────

export function Conductor({ messages, isVisible, onSend }: ConductorProps) {
  const [inputValue, setInputValue] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('watcher')
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!isVisible) return null

  function handleSend() {
    const trimmed = inputValue.trim()
    if (!trimmed) return
    onSend(trimmed)
    setInputValue('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
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
          }}
        />
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
      </div>
    </div>
  )
}

export default Conductor
