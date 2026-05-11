import { useEffect, useState } from 'react'
import { useAppStore } from '../store/app-store'
import type { Theme, ConductorDefaultVisibility } from '../store/app-store'
import { ThemeSwatch } from './ThemeSwatch'
import { GitSettings } from './settings/GitSettings'
import { AboutPage } from './settings/AboutPage'
import { PipelineSettings } from './settings/PipelineSettings'
import type { PipelineSection } from './settings/PipelineSettings'

export interface SettingsProps {
  isOpen: boolean
  onClose: () => void
}

// ── Nav items ─────────────────────────────────────────────────────────────────

interface NavItem {
  label: string
  id: string
  disabled: boolean
}

interface NavGroup {
  groupLabel: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    groupLabel: 'General',
    items: [
      { label: 'Appearance', id: 'appearance', disabled: false },
      { label: 'Keyboard Shortcuts', id: 'keyboard', disabled: true },
      { label: 'Notifications', id: 'notifications', disabled: true },
    ],
  },
  {
    groupLabel: 'Pipeline',
    items: [
      { label: 'Agents', id: 'agents', disabled: false },
      { label: 'Watcher', id: 'watcher', disabled: false },
      { label: 'Git & Branches', id: 'git', disabled: false },
    ],
  },
  {
    groupLabel: 'Advanced',
    items: [
      { label: 'About', id: 'about', disabled: false },
    ],
  },
]

// ── Appearance page options ───────────────────────────────────────────────────

const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'dark', label: 'Dark' },
  { value: 'light', label: 'Light' },
]

const CONDUCTOR_OPTIONS: { value: ConductorDefaultVisibility; label: string }[] = [
  { value: 'always', label: 'Always visible' },
  { value: 'auto', label: 'Auto' },
  { value: 'hidden', label: 'Hidden' },
]

// ── Theme card ────────────────────────────────────────────────────────────────

function ThemeCard({
  theme,
  label,
  isActive,
  onClick,
}: {
  theme: Theme
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={isActive}
      style={{
        flex: '1 1 0',
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: 8,
        borderRadius: 9,
        border: `2px solid ${isActive ? 'var(--t-purple)' : 'var(--t-border)'}`,
        background: isActive
          ? 'color-mix(in srgb, var(--t-purple) 6%, var(--t-surface))'
          : 'var(--t-surface)',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'border-color var(--t-dur-fast) var(--t-ease), background var(--t-dur-fast) var(--t-ease)',
      }}
    >
      <ThemeSwatch theme={theme} />
      <span
        style={{
          fontSize: 12,
          fontWeight: isActive ? 600 : 400,
          color: 'var(--t-text)',
          textAlign: 'center',
          width: '100%',
        }}
      >
        {label}
      </span>
    </button>
  )
}

// ── Appearance page ───────────────────────────────────────────────────────────

function AppearancePage() {
  const theme = useAppStore((s) => s.theme)
  const conductorDefaultVisibility = useAppStore((s) => s.conductorDefaultVisibility)
  const setTheme = useAppStore((s) => s.setTheme)
  const setConductorDefaultVisibility = useAppStore((s) => s.setConductorDefaultVisibility)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* ── Theme section ── */}
      <section>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t-text)', marginBottom: 2 }}>
            Theme
          </div>
          <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>
            Choose your preferred color scheme
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {THEME_OPTIONS.map(({ value, label }) => (
            <ThemeCard
              key={value}
              theme={value}
              label={label}
              isActive={theme === value}
              onClick={() => setTheme(value)}
            />
          ))}
        </div>
      </section>

      {/* ── Conductor Panel section ── */}
      <section>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t-text)', marginBottom: 2 }}>
            Conductor Panel
          </div>
          <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>
            Default visibility
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {CONDUCTOR_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setConductorDefaultVisibility(value)}
              aria-pressed={conductorDefaultVisibility === value}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--t-radius-sm)',
                border: `1px solid ${conductorDefaultVisibility === value ? 'var(--t-purple)' : 'var(--t-border)'}`,
                background: conductorDefaultVisibility === value
                  ? 'color-mix(in srgb, var(--t-purple) 12%, transparent)'
                  : 'var(--t-surface)',
                color: conductorDefaultVisibility === value ? 'var(--t-purple)' : 'var(--t-text-2)',
                fontSize: 12,
                fontWeight: conductorDefaultVisibility === value ? 600 : 400,
                cursor: 'pointer',
                transition: 'border-color var(--t-dur-fast) var(--t-ease), background var(--t-dur-fast) var(--t-ease)',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

// ── Page title map ────────────────────────────────────────────────────────────

const PAGE_TITLES: Record<string, string> = {
  appearance: 'Appearance',
  agents:     'Agents',
  watcher:    'Watcher',
  git:        'Git & Branches',
  about:      'About',
}

// ── Settings modal ────────────────────────────────────────────────────────────

export function Settings({ isOpen, onClose }: SettingsProps) {
  const [activePage, setActivePage] = useState<string>('appearance')

  // Close on Escape
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

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(10, 15, 26, 0.75)',
          zIndex: 100,
          animation: 'settings-fade-in var(--t-dur-base) var(--t-ease) both',
        }}
      />

      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 101,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            width: 720,
            height: 480,
            background: 'var(--t-bg)',
            borderRadius: 'var(--t-radius-xl)',
            border: '1px solid var(--t-border)',
            display: 'flex',
            overflow: 'hidden',
            pointerEvents: 'auto',
            boxShadow: '0 24px 64px rgba(0, 0, 0, 0.3)',
            animation: 'settings-slide-in var(--t-dur-base) var(--t-ease) both',
          }}
        >
          {/* ── Left nav sidebar ── */}
          <div
            style={{
              width: 200,
              minWidth: 200,
              background: 'var(--t-bg)',
              borderRight: '1px solid var(--t-border)',
              display: 'flex',
              flexDirection: 'column',
              padding: '16px 8px',
              overflowY: 'auto',
              gap: 16,
            }}
          >
            {NAV_GROUPS.map((group) => (
              <div key={group.groupLabel}>
                {/* Group label */}
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.10em',
                    color: 'var(--t-text-3)',
                    padding: '0 8px 4px',
                  }}
                >
                  {group.groupLabel}
                </div>

                {/* Nav items */}
                {group.items.map((item) => {
                  const isActive = item.id === activePage
                  return (
                    <button
                      key={item.id}
                      disabled={item.disabled}
                      onClick={() => { if (!item.disabled) setActivePage(item.id) }}
                      aria-current={isActive ? 'page' : undefined}
                      style={{
                        display: 'block',
                        width: '100%',
                        padding: '6px 8px',
                        borderRadius: 9,
                        border: 'none',
                        background: isActive ? 'var(--t-surface)' : 'transparent',
                        color: item.disabled
                          ? 'var(--t-text-3)'
                          : isActive
                          ? 'var(--t-text)'
                          : 'var(--t-text-2)',
                        fontSize: 12,
                        fontWeight: isActive ? 500 : 400,
                        textAlign: 'left',
                        cursor: item.disabled ? 'default' : 'pointer',
                        opacity: item.disabled ? 0.5 : 1,
                        transition: 'background var(--t-dur-fast) var(--t-ease)',
                      }}
                    >
                      {item.label}
                      {item.disabled && (
                        <span style={{ color: 'var(--t-text-3)', marginLeft: 4 }}>(soon)</span>
                      )}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>

          {/* ── Right content area ── */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Header bar */}
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
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--t-text)',
                }}
              >
                {PAGE_TITLES[activePage] ?? activePage}
              </span>

              {/* Close button */}
              <button
                onClick={onClose}
                aria-label="Close settings"
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
                  transition: 'background var(--t-dur-fast) var(--t-ease)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--t-surface)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                }}
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

            {/* Page content */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '20px',
              }}
            >
              {activePage === 'appearance' && <AppearancePage />}
              {(activePage === 'agents' || activePage === 'watcher') && (
                <PipelineSettings section={activePage as PipelineSection} />
              )}
              {activePage === 'git' && <GitSettings />}
              {activePage === 'about' && <AboutPage />}
            </div>
          </div>
        </div>
      </div>

      {/* Keyframe styles injected inline */}
      <style>{`
        @keyframes settings-fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes settings-slide-in {
          from { opacity: 0; transform: scale(0.96) translateY(8px); }
          to   { opacity: 1; transform: scale(1)    translateY(0); }
        }
      `}</style>
    </>
  )
}

export default Settings
