import { useEffect, useRef, useState } from 'react'

export interface NewTaskDialogProps {
  isOpen: boolean
  onClose: () => void
  onCreated: () => void
}

const SUGGESTED_TAGS = ['frontend', 'security'] as const

export function NewTaskDialog({ isOpen, onClose, onCreated }: NewTaskDialogProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())
  const [deps, setDeps] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const titleRef = useRef<HTMLInputElement>(null)

  // Autofocus title input when dialog opens
  useEffect(() => {
    if (isOpen) {
      const t = setTimeout(() => titleRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [isOpen])

  // Reset form state when dialog closes
  useEffect(() => {
    if (!isOpen) {
      setTitle('')
      setDescription('')
      setSelectedTags(new Set())
      setDeps('')
      setError(null)
      setSubmitting(false)
    }
  }, [isOpen])

  // Close on Escape (capture phase so it runs before App's handler)
  useEffect(() => {
    if (!isOpen) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown, true)
    return () => document.removeEventListener('keydown', handleKeyDown, true)
  }, [isOpen, onClose])

  async function handleCreate() {
    if (!title.trim() || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await window.debussy.tasks.create(title.trim(), description.trim())
      if (result.success) {
        onCreated()
        onClose()
      } else {
        setError('Failed to create task. Please try again.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.')
    } finally {
      setSubmitting(false)
    }
  }

  function toggleTag(tag: string) {
    setSelectedTags((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }

  if (!isOpen) return null

  const canCreate = title.trim().length > 0 && !submitting

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          zIndex: 200,
          animation: 'ntd-fade-in 200ms var(--t-ease) both',
        }}
      />

      {/* Centering shell (pointer-events:none so backdrop click-through works) */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 201,
          pointerEvents: 'none',
        }}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label="New Task"
          style={{
            width: 520,
            background: 'var(--t-bg)',
            borderRadius: 'var(--t-radius-xl)',
            border: '1px solid var(--t-border)',
            boxShadow: '0 24px 64px rgba(0, 0, 0, 0.35)',
            pointerEvents: 'auto',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'ntd-slide-in 200ms var(--t-ease) both',
          }}
        >
          {/* ── Header ── */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 20px 12px',
              borderBottom: '1px solid var(--t-border)',
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--t-text)' }}>
              New Task
            </span>
            <button
              onClick={onClose}
              aria-label="Close"
              style={{
                width: 24,
                height: 24,
                borderRadius: 6,
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--t-text-3)',
                padding: 0,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--t-surface)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path
                  d="M1 1l10 10M11 1L1 11"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>

          {/* ── Body ── */}
          <div
            style={{
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              overflowY: 'auto',
            }}
          >
            {/* Title input */}
            <input
              ref={titleRef}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
              placeholder="Task title"
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '8px 12px',
                background: 'var(--t-surface)',
                border: '1px solid var(--t-border)',
                borderRadius: 'var(--t-radius-sm)',
                color: 'var(--t-text)',
                fontSize: '14px',
                outline: 'none',
                fontFamily: 'inherit',
                transition: 'border-color var(--t-dur-fast) var(--t-ease)',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--t-purple)' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--t-border)' }}
            />

            {/* Description textarea */}
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Task description (acceptance criteria, files to modify, constraints...)"
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '8px 12px',
                background: 'var(--t-surface)',
                border: '1px solid var(--t-border)',
                borderRadius: 'var(--t-radius-sm)',
                color: 'var(--t-text)',
                fontSize: '13px',
                minHeight: '120px',
                resize: 'vertical',
                outline: 'none',
                fontFamily: 'inherit',
                lineHeight: 1.5,
                transition: 'border-color var(--t-dur-fast) var(--t-ease)',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--t-purple)' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--t-border)' }}
            />

            {/* Tags */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--t-text-3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: 8,
                }}
              >
                Tags
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {SUGGESTED_TAGS.map((tag) => {
                  const active = selectedTags.has(tag)
                  return (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      aria-pressed={active}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 'var(--t-radius-pill)',
                        border: `1px solid ${active ? 'var(--t-purple)' : 'var(--t-border)'}`,
                        background: active
                          ? 'color-mix(in srgb, var(--t-purple) 12%, transparent)'
                          : 'var(--t-surface)',
                        color: active ? 'var(--t-purple)' : 'var(--t-text-2)',
                        fontSize: 12,
                        fontWeight: active ? 600 : 400,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        transition:
                          'border-color var(--t-dur-fast) var(--t-ease), background var(--t-dur-fast) var(--t-ease)',
                      }}
                    >
                      {tag}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Dependencies */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--t-text-3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: 8,
                }}
              >
                Dependencies
              </div>
              <input
                type="text"
                value={deps}
                onChange={(e) => setDeps(e.target.value)}
                placeholder="e.g. DBS-1, DBS-3"
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 12px',
                  background: 'var(--t-surface)',
                  border: '1px solid var(--t-border)',
                  borderRadius: 'var(--t-radius-sm)',
                  color: 'var(--t-text)',
                  fontSize: '13px',
                  outline: 'none',
                  fontFamily: 'inherit',
                  transition: 'border-color var(--t-dur-fast) var(--t-ease)',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--t-purple)' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--t-border)' }}
              />
            </div>

            {/* Inline error message */}
            {error && (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--t-error)',
                  padding: '8px 12px',
                  background: 'color-mix(in srgb, var(--t-error) 8%, transparent)',
                  borderRadius: 'var(--t-radius-sm)',
                  border: '1px solid color-mix(in srgb, var(--t-error) 20%, transparent)',
                }}
              >
                {error}
              </div>
            )}
          </div>

          {/* ── Footer ── */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
              padding: '12px 20px',
              borderTop: '1px solid var(--t-border)',
              flexShrink: 0,
            }}
          >
            <button
              onClick={onClose}
              style={{
                padding: '6px 16px',
                background: 'transparent',
                border: '1px solid var(--t-border)',
                borderRadius: 'var(--t-radius-sm)',
                color: 'var(--t-text-2)',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!canCreate}
              style={{
                padding: '6px 16px',
                background: canCreate ? 'var(--t-gradient)' : 'var(--t-surface)',
                border: 'none',
                borderRadius: 'var(--t-radius-sm)',
                color: canCreate ? '#ffffff' : 'var(--t-text-3)',
                fontSize: 13,
                fontWeight: 600,
                cursor: canCreate ? 'pointer' : 'not-allowed',
                opacity: canCreate ? 1 : 0.5,
                fontFamily: 'inherit',
                transition: 'opacity var(--t-dur-fast) var(--t-ease)',
              }}
            >
              {submitting ? 'Creating…' : 'Create'}
            </button>
          </div>
        </div>
      </div>

      {/* Keyframe animations */}
      <style>{`
        @keyframes ntd-fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes ntd-slide-in {
          from { opacity: 0; transform: scale(0.96) translateY(8px); }
          to   { opacity: 1; transform: scale(1)    translateY(0); }
        }
      `}</style>
    </>
  )
}

export default NewTaskDialog
