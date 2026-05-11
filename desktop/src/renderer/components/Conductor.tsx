import { useEffect, useRef, useState } from 'react'
import { ConductorMessage } from '../../shared/types'
import { useAppStore } from '../store/app-store'
import { ImagePreview } from './ImagePreview'
import { useImageAttachments } from '../hooks/useImageAttachments'
import { UserBubble, AssistantBubble, SystemBubble, StreamingIndicator } from './ConductorMessages'

// ── Types ────────────────────────────────────────────────────────────────────

type TabKey = 'watcher' | 'agents'

interface ConductorProps {
  messages: ConductorMessage[]
  isVisible: boolean
  onSend: (message: string, imagePaths: string[], tempPaths: string[], previewUrls: string[]) => void
}

// ── Conductor ────────────────────────────────────────────────────────────────

export function Conductor({ messages, isVisible, onSend }: ConductorProps) {
  const [inputValue, setInputValue] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('watcher')
  const [streamingContent, setStreamingContent] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionIdCopied, setSessionIdCopied] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const isStreaming = useAppStore((s) => s.conductorStreaming)
  const setConductorStreaming = useAppStore((s) => s.setConductorStreaming)
  const addConductorMessage = useAppStore((s) => s.addConductorMessage)
  const clearConductorMessages = useAppStore((s) => s.clearConductorMessages)

  const {
    attachedImages,
    isDragOver,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    handleOpenFilePicker,
    handleRemoveImage,
    clearImages,
    revokeAndClearImages,
    getImagePayload,
  } = useImageAttachments(inputRef)

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

  // ── Auto-resume indicator on mount ─────────────────────────────────────────

  useEffect(() => {
    window.debussy.conductor.getSessionId().then(({ sessionId: id }) => {
      setSessionId(id)
      // If a session existed before this render, show "Resumed" notice
      if (id && messages.length === 0) {
        addConductorMessage({
          id: `cm-sys-resume-${Date.now()}`,
          role: 'system',
          content: 'Resumed previous session',
          timestamp: Date.now(),
        })
      }
    })
  // Run once on mount only
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-scroll to bottom when messages or streaming content change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  if (!isVisible) return null

  // ── Core actions ───────────────────────────────────────────────────────────

  function handleSend() {
    const trimmed = inputValue.trim()
    if ((!trimmed && attachedImages.length === 0) || isStreaming) return

    const { imagePaths, tempPaths, previewUrls } = getImagePayload()
    // Pass preview URLs to parent so they appear in the chat history bubble
    onSend(trimmed, imagePaths, tempPaths, previewUrls)

    // Keep object URLs alive — parent renders them; don't revoke here.
    setInputValue('')
    setStreamingContent('')
    clearImages()
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
    revokeAndClearImages()
    const result = await window.debussy.conductor.clearContext()
    if (result.sessionId) setSessionId(result.sessionId)
    addConductorMessage({
      id: `cm-sys-clear-${Date.now()}`,
      role: 'system',
      content: 'Context cleared — project history loaded',
      timestamp: Date.now(),
    })
  }

  function handleCopySessionId() {
    if (!sessionId) return
    navigator.clipboard.writeText(sessionId).then(() => {
      setSessionIdCopied(true)
      setTimeout(() => setSessionIdCopied(false), 1500)
    })
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        width: 320,
        flexShrink: 0,
        background: isDragOver ? 'rgba(108, 92, 231, 0.06)' : 'var(--t-surface)',
        borderLeft: '1px solid var(--t-border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        outline: isDragOver ? '2px dashed var(--t-purple)' : 'none',
        outlineOffset: -2,
        transition: 'background var(--t-dur-fast)',
        position: 'relative',
      }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header — two-row layout */}
      <div
        style={{
          flexShrink: 0,
          borderBottom: '1px solid var(--t-border)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Row 1 (36px): Title + New Session */}
        <div
          style={{
            height: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 14px',
            gap: 12,
          }}
        >
          {/* Title + session ID subtitle */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--t-text)',
                letterSpacing: '-0.01em',
                lineHeight: 1,
              }}
            >
              Conductor
            </span>
            {sessionId && (
              <button
                onClick={handleCopySessionId}
                title={sessionIdCopied ? 'Copied!' : 'Click to copy session ID'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  color: sessionIdCopied ? 'var(--t-purple)' : 'var(--t-text-3)',
                  fontSize: 11,
                  fontFamily: 'ui-monospace, monospace',
                  letterSpacing: '0.01em',
                  textAlign: 'left',
                  lineHeight: 1,
                  transition: 'color var(--t-dur-fast)',
                }}
              >
                {sessionIdCopied ? '✓ copied' : sessionId.slice(0, 8) + '…'}
              </button>
            )}
          </div>

          {/* New Session button */}
          <button
            onClick={handleNewSession}
            title="New session — auto-loads project context"
            style={{
              height: 26,
              padding: '0 12px',
              background: 'transparent',
              border: '1px solid var(--t-border)',
              borderRadius: 9,
              cursor: 'pointer',
              color: 'var(--t-text-2)',
              fontSize: 11,
              fontWeight: 500,
              fontFamily: 'inherit',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              transition: 'color var(--t-dur-fast), border-color var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--t-text)'
              e.currentTarget.style.borderColor = 'var(--t-text-3)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--t-text-2)'
              e.currentTarget.style.borderColor = 'var(--t-border)'
            }}
          >
            New Session
          </button>
        </div>

        {/* Row 2 (32px): Watcher / Agents pill tabs */}
        <div
          style={{
            height: 32,
            display: 'flex',
            alignItems: 'center',
            padding: '0 10px',
            gap: 2,
          }}
        >
          {(['watcher', 'agents'] as TabKey[]).map((tab) => {
            const isActive = activeTab === tab
            const label = tab === 'watcher' ? 'Watcher' : 'Agents'
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '4px 14px',
                  borderRadius: 100,
                  border: 'none',
                  background: isActive
                    ? 'color-mix(in srgb, var(--t-purple) 14%, var(--t-bg))'
                    : 'transparent',
                  color: isActive ? 'var(--t-purple)' : 'var(--t-text-3)',
                  fontSize: 11,
                  fontWeight: isActive ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'background var(--t-dur-fast), color var(--t-dur-fast)',
                  fontFamily: 'inherit',
                  lineHeight: 1.4,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--t-text-2)'
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.color = 'var(--t-text-3)'
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
          msg.role === 'system' ? (
            <SystemBubble key={msg.id} message={msg} />
          ) : msg.role === 'user' ? (
            <UserBubble key={msg.id} message={msg} />
          ) : (
            <AssistantBubble key={msg.id} message={msg} />
          )
        )}
        {isStreaming && <StreamingIndicator content={streamingContent} />}
        <div ref={chatEndRef} />
      </div>

      {/* Attached-image strip — shown above the input when images are queued */}
      {attachedImages.length > 0 && (
        <div
          style={{
            flexShrink: 0,
            borderTop: '1px solid var(--t-border)',
            padding: '8px 12px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          {attachedImages.map((img) => (
            <ImagePreview
              key={img.id}
              src={img.previewUrl}
              onRemove={() => handleRemoveImage(img.id)}
            />
          ))}
        </div>
      )}

      {/* Input bar */}
      <div
        style={{
          flexShrink: 0,
          borderTop: attachedImages.length > 0 ? 'none' : '1px solid var(--t-border)',
          padding: '10px 12px',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}
      >
        {/* Paperclip / attachment button */}
        <button
          onClick={handleOpenFilePicker}
          aria-label="Attach image"
          title="Attach image"
          disabled={isStreaming}
          style={{
            width: 28,
            height: 28,
            flexShrink: 0,
            background: 'transparent',
            border: '1px solid var(--t-border)',
            borderRadius: 8,
            cursor: isStreaming ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--t-text-3)',
            opacity: isStreaming ? 0.4 : 1,
            transition: 'color var(--t-dur-fast), border-color var(--t-dur-fast)',
          }}
          onMouseEnter={(e) => {
            if (!isStreaming) e.currentTarget.style.color = 'var(--t-text)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--t-text-3)'
          }}
        >
          {/* Paperclip icon */}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path
              d="M10.5 5.5L5.5 10.5C4.4 11.6 2.6 11.6 1.5 10.5C0.4 9.4 0.4 7.6 1.5 6.5L6.5 1.5C7.2 0.8 8.3 0.8 9 1.5C9.7 2.2 9.7 3.3 9 4L4.5 8.5C4.2 8.8 3.7 8.8 3.4 8.5C3.1 8.2 3.1 7.7 3.4 7.4L7.5 3.3"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={attachedImages.length > 0 ? 'Add a message…' : 'Talk to conductor...'}
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
            disabled={inputValue.trim() === '' && attachedImages.length === 0}
            style={{
              width: 32,
              height: 32,
              flexShrink: 0,
              background: 'var(--t-gradient)',
              border: 'none',
              borderRadius: 9,
              cursor: (inputValue.trim() === '' && attachedImages.length === 0) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              opacity: (inputValue.trim() === '' && attachedImages.length === 0) ? 0.4 : 1,
              transition: 'opacity var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => {
              if (inputValue.trim() !== '' || attachedImages.length > 0) {
                e.currentTarget.style.opacity = '0.85'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity =
                inputValue.trim() === '' && attachedImages.length === 0 ? '0.4' : '1'
            }}
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
