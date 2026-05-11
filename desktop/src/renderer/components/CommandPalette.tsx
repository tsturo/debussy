import { useEffect, useRef, useState } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PaletteAction {
  id: string
  name: string
  category: string
  shortcut?: string | null
  action: () => void
}

interface CommandPaletteProps {
  isOpen: boolean
  actions: PaletteAction[]
  onClose: () => void
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function filterActions(actions: PaletteAction[], query: string): PaletteAction[] {
  if (!query.trim()) return actions
  const q = query.toLowerCase()
  return actions.filter((a) => a.name.toLowerCase().includes(q))
}

function groupByCategory(actions: PaletteAction[]): Array<{ category: string; items: PaletteAction[] }> {
  const map = new Map<string, PaletteAction[]>()
  for (const action of actions) {
    const list = map.get(action.category) ?? []
    list.push(action)
    map.set(action.category, list)
  }
  return Array.from(map.entries()).map(([category, items]) => ({ category, items }))
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ShortcutHint({ shortcut }: { shortcut: string }) {
  return (
    <kbd
      style={{
        fontSize: 12,
        color: 'var(--t-text-3)',
        background: 'color-mix(in srgb, var(--t-border) 60%, transparent)',
        border: '1px solid var(--t-border)',
        borderRadius: 5,
        padding: '1px 5px',
        fontFamily: 'inherit',
        letterSpacing: '0.02em',
        flexShrink: 0,
      }}
    >
      {shortcut}
    </kbd>
  )
}

function ActionRow({
  action,
  isActive,
  onExecute,
  onHover,
}: {
  action: PaletteAction
  isActive: boolean
  onExecute: () => void
  onHover: () => void
}) {
  return (
    <button
      onMouseEnter={onHover}
      onClick={onExecute}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        width: '100%',
        padding: '7px 12px',
        border: 'none',
        background: isActive ? 'color-mix(in srgb, var(--t-text) 6%, transparent)' : 'transparent',
        cursor: 'pointer',
        textAlign: 'left',
        borderRadius: 8,
        transition: 'background var(--t-dur-fast) var(--t-ease)',
      }}
    >
      {/* Action name */}
      <span
        style={{
          flex: 1,
          fontSize: 13,
          color: 'var(--t-text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {action.name}
      </span>

      {/* Keyboard shortcut hint */}
      {action.shortcut && <ShortcutHint shortcut={action.shortcut} />}
    </button>
  )
}

function CategoryLabel({ label }: { label: string }) {
  return (
    <div
      style={{
        fontSize: 12,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.10em',
        color: 'var(--t-text-3)',
        padding: '8px 12px 3px',
        userSelect: 'none',
      }}
    >
      {label}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function CommandPalette({ isOpen, actions, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Reset state when palette opens/closes
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setActiveIndex(0)
      // Autofocus on next tick so the element is rendered
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [isOpen])

  const filtered = filterActions(actions, query)
  const groups = groupByCategory(filtered)

  // Flat list of actions for keyboard navigation
  const flatList = filtered

  // Reset active index when query changes
  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return
    const activeEl = listRef.current.querySelector('[data-active="true"]') as HTMLElement | null
    activeEl?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, flatList.length - 1))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const action = flatList[activeIndex]
      if (action) {
        action.action()
        onClose()
      }
      return
    }
  }

  function executeAction(action: PaletteAction) {
    action.action()
    onClose()
  }

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 900,
          background: 'rgba(0, 0, 0, 0.4)',
        }}
      />

      {/* Palette modal */}
      <div
        role="dialog"
        aria-label="Command palette"
        aria-modal="true"
        style={{
          position: 'fixed',
          top: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 901,
          width: 480,
          maxWidth: 'calc(100vw - 32px)',
          background: 'var(--t-surface)',
          border: '1px solid var(--t-border)',
          borderRadius: 'var(--t-radius-xl)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.24), 0 2px 8px rgba(0, 0, 0, 0.12)',
          overflow: 'hidden',
        }}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div
          style={{
            padding: '10px 12px',
            borderBottom: '1px solid var(--t-border)',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command..."
            style={{
              width: '100%',
              border: 'none',
              outline: 'none',
              background: 'var(--t-bg)',
              fontSize: 14,
              color: 'var(--t-text)',
              fontFamily: 'inherit',
            }}
          />
        </div>

        {/* Action list */}
        <div
          ref={listRef}
          style={{
            maxHeight: 360,
            overflowY: 'auto',
            padding: '4px',
          }}
        >
          {flatList.length === 0 ? (
            <div
              style={{
                padding: '24px 12px',
                textAlign: 'center',
                fontSize: 13,
                color: 'var(--t-text-3)',
              }}
            >
              No results
            </div>
          ) : (
            groups.map(({ category, items }) => {
              return (
                <div key={category}>
                  <CategoryLabel label={category} />
                  {items.map((action) => {
                    const flatIdx = flatList.indexOf(action)
                    return (
                      <div key={action.id} data-active={flatIdx === activeIndex ? 'true' : undefined}>
                        <ActionRow
                          action={action}
                          isActive={flatIdx === activeIndex}
                          onExecute={() => executeAction(action)}
                          onHover={() => setActiveIndex(flatIdx)}
                        />
                      </div>
                    )
                  })}
                </div>
              )
            })
          )}
        </div>
      </div>
    </>
  )
}

export default CommandPalette
