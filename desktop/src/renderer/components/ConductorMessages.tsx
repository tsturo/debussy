import { ConductorMessage } from '../../shared/types'
import { SentImageThumbnail } from './ImagePreview'

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

// ── Components ────────────────────────────────────────────────────────────────

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

export function UserBubble({ message }: { message: ConductorMessage }) {
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
      {/* Image thumbnails sent with this message */}
      {message.images && message.images.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: message.content ? 6 : 0 }}>
          {message.images.map((url, i) => (
            <SentImageThumbnail key={i} src={url} />
          ))}
        </div>
      )}
      {message.content}
    </div>
  )
}

export function AssistantBubble({ message }: { message: ConductorMessage }) {
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

/** Faded system notice shown for session events (clear, etc.). */
export function SystemBubble({ message }: { message: ConductorMessage }) {
  return (
    <div
      style={{
        alignSelf: 'center',
        fontSize: 10,
        color: 'var(--t-text-3)',
        padding: '3px 10px',
        background: 'var(--t-bg)',
        border: '1px solid var(--t-border)',
        borderRadius: 20,
        opacity: 0.75,
        userSelect: 'none',
      }}
    >
      {message.content}
    </div>
  )
}

/**
 * Rich session-resume card shown on app launch when a previous session exists.
 * Styled as a subtle card (not the default pill) so it's present but unobtrusive.
 */
export function ResumeCard({ message }: { message: ConductorMessage }) {
  const lines = message.content.split('\n')
  return (
    <div
      style={{
        alignSelf: 'stretch',
        background: 'var(--t-surface)',
        border: '1px solid var(--t-border)',
        borderRadius: 12,
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        userSelect: 'none',
        color: 'var(--t-text-3)',
        fontSize: 10,
        lineHeight: 1.6,
      }}
    >
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            fontFamily: i === 0 ? 'ui-monospace, SFMono-Regular, Menlo, monospace' : 'inherit',
            fontWeight: i === 0 ? 500 : 400,
          }}
        >
          {line || ' '}
        </div>
      ))}
    </div>
  )
}

/** Animated pulsing dots shown while the conductor is streaming a response. */
export function StreamingIndicator({ content }: { content: string }) {
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
