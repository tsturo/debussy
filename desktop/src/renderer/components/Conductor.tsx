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

// ── Session menu ─────────────────────────────────────────────────────────────

interface SessionMenuProps {
  sessionId: string | null
  onClearContext: () => void
  onNewBlankSession: () => void
  onClose: () => void
}

function SessionMenu({ sessionId, onClearContext, onNewBlankSession, onClose }: SessionMenuProps) {
  const [copied, setCopied] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  function handleCopySessionId() {
    if (!sessionId) return
    navigator.clipboard.writeText(sessionId).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const truncated = sessionId ? sessionId.slice(0, 8) + '…' : '—'

  return (
    <div
      ref={menuRef}
      style={{
        position: 'absolute',
        top: 42,
        right: 10,
        zIndex: 100,
        background: 'var(--t-surface)',
        border: '1px solid var(--t-border)',
        borderRadius: 10,
        boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
        minWidth: 200,
        overflow: 'hidden',
      }}
    >
      <MenuItem
        label="Clear & Reload Context"
        description="Start fresh, auto-send project history"
        onClick={() => { onClearContext(); onClose() }}
      />
      <MenuItem
        label="New Blank Session"
        description="Start completely blank"
        onClick={() => { onNewBlankSession(); onClose() }}
      />

      {/* Separator */}
      <div style={{ height: 1, background: 'var(--t-border)', margin: '2px 0' }} />

      {/* Session ID row */}
      <button
        onClick={handleCopySessionId}
        title={sessionId ?? 'No session yet'}
        style={{
          width: '100%',
          background: 'transparent',
          border: 'none',
          padding: '7px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          cursor: sessionId ? 'pointer' : 'default',
          color: 'var(--t-text-3)',
          fontSize: 10,
          fontFamily: 'inherit',
          textAlign: 'left',
        }}
      >
        <span>Session: <span style={{ fontFamily: 'ui-monospace, monospace' }}>{truncated}</span></span>
        {sessionId && (
          <span style={{ fontSize: 9, opacity: 0.7 }}>
            {copied ? '✓ Copied' : 'Click to copy'}
          </span>
        )}
      </button>
    </div>
  )
}

function MenuItem({
  label,
  description,
  onClick,
}: {
  label: string
  description: string
  onClick: () => void
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%',
        background: hovered ? 'var(--t-bg)' : 'transparent',
        border: 'none',
        padding: '8px 12px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 1,
        cursor: 'pointer',
        color: 'var(--t-text)',
        fontSize: 11,
        fontFamily: 'inherit',
        textAlign: 'left',
        transition: 'background var(--t-dur-fast)',
      }}
    >
      <span style={{ fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{description}</span>
    </button>
  )
}

// ── Conductor ────────────────────────────────────────────────────────────────

export function Conductor({ messages, isVisible, onSend }: ConductorProps) {
  const [inputValue, setInputValue] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('watcher')
  const [streamingContent, setStreamingContent] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
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

  async function handleClearContext() {
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

  async function handleNewBlankSession() {
    window.debussy.conductor.cancel()
    setStreamingContent('')
    setConductorStreaming(false)
    clearConductorMessages()
    revokeAndClearImages()
    const result = await window.debussy.conductor.newSession()
    if (result.sessionId) setSessionId(result.sessionId)
    addConductorMessage({
      id: `cm-sys-blank-${Date.now()}`,
      role: 'system',
      content: 'New blank session started',
      timestamp: Date.now(),
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
          {/* Session menu button (three-dot) */}
          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Session options"
            title="Session options"
            style={{
              width: 26,
              height: 26,
              flexShrink: 0,
              background: menuOpen ? 'var(--t-bg)' : 'transparent',
              border: '1px solid var(--t-border)',
              borderRadius: 8,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: menuOpen ? 'var(--t-text)' : 'var(--t-text-3)',
              transition: 'color var(--t-dur-fast), border-color var(--t-dur-fast), background var(--t-dur-fast)',
            }}
            onMouseEnter={(e) => {
              if (!menuOpen) {
                e.currentTarget.style.color = 'var(--t-text)'
                e.currentTarget.style.borderColor = 'var(--t-text-3)'
              }
            }}
            onMouseLeave={(e) => {
              if (!menuOpen) {
                e.currentTarget.style.color = 'var(--t-text-3)'
                e.currentTarget.style.borderColor = 'var(--t-border)'
              }
            }}
          >
            {/* Three-dot icon */}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <circle cx="2.5" cy="6" r="1.2" fill="currentColor" />
              <circle cx="6" cy="6" r="1.2" fill="currentColor" />
              <circle cx="9.5" cy="6" r="1.2" fill="currentColor" />
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

      {/* Session dropdown menu */}
      {menuOpen && (
        <SessionMenu
          sessionId={sessionId}
          onClearContext={handleClearContext}
          onNewBlankSession={handleNewBlankSession}
          onClose={() => setMenuOpen(false)}
        />
      )}

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
