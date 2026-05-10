import { useCallback, useEffect, useRef, useState } from 'react'
import { ConductorMessage } from '../../shared/types'
import { useAppStore } from '../store/app-store'
import { ImagePreview, SentImageThumbnail } from './ImagePreview'

// ── Types ────────────────────────────────────────────────────────────────────

type TabKey = 'watcher' | 'agents'

interface ConductorProps {
  messages: ConductorMessage[]
  isVisible: boolean
  onSend: (message: string, imagePaths: string[], tempPaths: string[], previewUrls: string[]) => void
}

/**
 * An image attached (but not yet sent) to the current input.
 * `path`       — absolute FS path passed to --image flag
 * `previewUrl` — object URL used for display (revoked on send/remove)
 * `isTemp`     — true when the file was created by uploadImage (clipboard),
 *                false for real files (drag-and-drop / file-picker)
 */
interface AttachedImage {
  id: string
  path: string
  previewUrl: string
  isTemp: boolean
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
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

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

  // ── Paste handler ──────────────────────────────────────────────────────────

  const handlePaste = useCallback(async (e: ClipboardEvent) => {
    // Only intercept when our input is focused
    if (document.activeElement !== inputRef.current) return

    const items = Array.from(e.clipboardData?.items ?? [])
    const imageItem = items.find((item) => item.type.startsWith('image/'))
    if (!imageItem) return  // non-image paste — let default text handling proceed

    e.preventDefault()

    const file = imageItem.getAsFile()
    if (!file) return

    const mimeType = imageItem.type
    const buffer = await file.arrayBuffer()

    try {
      const path = await window.debussy.conductor.uploadImage(buffer, mimeType)
      const previewUrl = URL.createObjectURL(file)
      setAttachedImages((prev) => [
        ...prev,
        { id: `img-${Date.now()}-${Math.random()}`, path, previewUrl, isTemp: true },
      ])
    } catch (err) {
      console.error('[conductor] uploadImage failed:', err)
    }
  }, [])

  useEffect(() => {
    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [handlePaste])

  if (!isVisible) return null

  // ── Core actions ───────────────────────────────────────────────────────────

  function revokePreviewUrls(images: AttachedImage[]) {
    for (const img of images) {
      URL.revokeObjectURL(img.previewUrl)
    }
  }

  function handleSend() {
    const trimmed = inputValue.trim()
    if ((!trimmed && attachedImages.length === 0) || isStreaming) return

    const imagePaths = attachedImages.map((img) => img.path)
    const tempPaths = attachedImages.filter((img) => img.isTemp).map((img) => img.path)
    const previewUrls = attachedImages.map((img) => img.previewUrl)

    // Pass preview URLs to parent so they appear in the chat history bubble
    onSend(trimmed, imagePaths, tempPaths, previewUrls)

    // Keep object URLs alive — parent renders them; don't revoke here.
    setInputValue('')
    setStreamingContent('')
    setAttachedImages([])
  }

  function handleRemoveImage(id: string) {
    setAttachedImages((prev) => {
      const img = prev.find((i) => i.id === id)
      if (img) URL.revokeObjectURL(img.previewUrl)
      return prev.filter((i) => i.id !== id)
    })
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
    revokePreviewUrls(attachedImages)
    setAttachedImages([])
    await window.debussy.conductor.newSession()
  }

  // ── File picker ────────────────────────────────────────────────────────────

  async function handleOpenFilePicker() {
    try {
      const paths = await window.debussy.conductor.openFileDialog()
      const newImages: AttachedImage[] = paths.map((p) => ({
        id: `img-${Date.now()}-${Math.random()}`,
        path: p,
        previewUrl: `file://${p}`,
        isTemp: false,
      }))
      setAttachedImages((prev) => [...prev, ...newImages])
    } catch (err) {
      console.error('[conductor] openFileDialog failed:', err)
    }
  }

  // ── Drag & drop ────────────────────────────────────────────────────────────

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    const hasFiles = Array.from(e.dataTransfer.types).includes('Files')
    if (!hasFiles) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    // Only clear when leaving the panel itself (not a child element)
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragOver(false)
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)

    const imageFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith('image/')
    )

    const newImages: AttachedImage[] = []
    for (const file of imageFiles) {
      // In Electron the File object has a `path` property
      const filePath = (file as File & { path: string }).path
      if (!filePath) {
        // Fallback: upload via IPC (e.g. when path is unavailable)
        try {
          const buffer = await file.arrayBuffer()
          const path = await window.debussy.conductor.uploadImage(buffer, file.type)
          const previewUrl = URL.createObjectURL(file)
          newImages.push({ id: `img-${Date.now()}-${Math.random()}`, path, previewUrl, isTemp: true })
        } catch (err) {
          console.error('[conductor] uploadImage (drop fallback) failed:', err)
        }
      } else {
        newImages.push({
          id: `img-${Date.now()}-${Math.random()}`,
          path: filePath,
          previewUrl: `file://${filePath}`,
          isTemp: false,
        })
      }
    }
    setAttachedImages((prev) => [...prev, ...newImages])
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
