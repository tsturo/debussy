import { useState, useEffect } from 'react'
import type { DebussyConfig, UiPrefs } from '../../../shared/types'

// ── Types ──────────────────────────────────────────────────────────────────────

export type PipelineSection = 'agents' | 'watcher'

interface PipelineSettingsProps {
  section: PipelineSection
}

// ── Constants ──────────────────────────────────────────────────────────────────

const AGENT_ROLES = [
  'developer',
  'reviewer',
  'integrator',
  'tester',
  'security-reviewer',
] as const

// ── Shared sub-components ──────────────────────────────────────────────────────

function SettingRow({
  label,
  description,
  children,
  error,
}: {
  label: string
  description?: string
  children: React.ReactNode
  error?: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 16,
        padding: '12px 0',
        borderBottom: '1px solid var(--t-border)',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--t-text)', marginBottom: 2 }}>
          {label}
        </div>
        {description && (
          <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>{description}</div>
        )}
        {error && (
          <div style={{ fontSize: 12, color: 'var(--t-red, #f87171)', marginTop: 4 }}>{error}</div>
        )}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  )
}

function NumberInput({
  value,
  min,
  max,
  onCommit,
  width,
}: {
  value: number
  min?: number
  max?: number
  onCommit: (n: number) => void
  width?: number
}) {
  const [draft, setDraft] = useState(String(value))

  // Keep draft in sync when value changes from outside (e.g., after save)
  useEffect(() => {
    setDraft(String(value))
  }, [value])

  function commit() {
    const n = Number(draft)
    if (!Number.isFinite(n)) {
      setDraft(String(value))
      return
    }
    if (min !== undefined && n < min) { setDraft(String(value)); return }
    if (max !== undefined && n > max) { setDraft(String(value)); return }
    onCommit(n)
  }

  return (
    <input
      type="number"
      value={draft}
      min={min}
      max={max}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur() } }}
      style={{
        width: width ?? 80,
        padding: '4px 8px',
        borderRadius: 'var(--t-radius-sm)',
        border: '1px solid var(--t-border)',
        background: 'var(--t-surface)',
        color: 'var(--t-text)',
        fontSize: 13,
        outline: 'none',
      }}
    />
  )
}

function TextInput({
  value,
  placeholder,
  onCommit,
  width,
}: {
  value: string
  placeholder?: string
  onCommit: (v: string) => void
  width?: number
}) {
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    setDraft(value)
  }, [value])

  function commit() {
    onCommit(draft.trim())
  }

  return (
    <input
      type="text"
      value={draft}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur() } }}
      style={{
        width: width ?? 180,
        padding: '4px 8px',
        borderRadius: 'var(--t-radius-sm)',
        border: '1px solid var(--t-border)',
        background: 'var(--t-surface)',
        color: 'var(--t-text)',
        fontSize: 13,
        outline: 'none',
      }}
    />
  )
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      style={{
        width: 38,
        height: 22,
        borderRadius: 11,
        border: 'none',
        background: checked ? 'var(--t-purple)' : 'var(--t-border)',
        cursor: 'pointer',
        position: 'relative',
        transition: 'background var(--t-dur-fast) var(--t-ease)',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 3,
          left: checked ? 19 : 3,
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: 'white',
          transition: 'left var(--t-dur-fast) var(--t-ease)',
        }}
      />
    </button>
  )
}

// ── Agents page ────────────────────────────────────────────────────────────────

function AgentsPage({
  config,
  setKey,
  errors,
}: {
  config: DebussyConfig
  setKey: (key: string, value: unknown) => Promise<void>
  errors: Record<string, string>
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <SettingRow
        label="Max total agents"
        description="Maximum number of agents running concurrently (1–8)"
        error={errors['max_total_agents']}
      >
        <NumberInput
          value={config.max_total_agents}
          min={1}
          max={8}
          onCommit={(n) => setKey('max_total_agents', n)}
        />
      </SettingRow>

      <SettingRow
        label="Agent timeout"
        description="Seconds before an agent is considered stuck"
        error={errors['agent_timeout']}
      >
        <NumberInput
          value={config.agent_timeout}
          min={1}
          onCommit={(n) => setKey('agent_timeout', n)}
          width={100}
        />
      </SettingRow>

      <SettingRow
        label="Agent provider"
        description="Path or name of the Claude binary (e.g. claude)"
        error={errors['agent_provider']}
      >
        <TextInput
          value={config.agent_provider}
          placeholder="claude"
          onCommit={(v) => setKey('agent_provider', v || 'claude')}
        />
      </SettingRow>

      {/* Role models table */}
      <div style={{ marginTop: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t-text)', marginBottom: 4 }}>
          Role models
        </div>
        <div style={{ fontSize: 12, color: 'var(--t-text-3)', marginBottom: 12 }}>
          Override the model used for each agent role. Leave blank to use the provider default.
        </div>
        <div
          style={{
            border: '1px solid var(--t-border)',
            borderRadius: 'var(--t-radius-sm)',
            overflow: 'hidden',
          }}
        >
          {AGENT_ROLES.map((role, i) => (
            <div
              key={role}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 12px',
                gap: 12,
                borderTop: i === 0 ? 'none' : '1px solid var(--t-border)',
                background: 'var(--t-surface)',
              }}
            >
              <span
                style={{
                  flex: 1,
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--t-text-2)',
                  fontFamily: 'var(--t-font-mono, monospace)',
                }}
              >
                {role}
              </span>
              <TextInput
                value={config.role_models[role] ?? ''}
                placeholder="default"
                onCommit={(v) => {
                  const updated = { ...config.role_models }
                  if (v) {
                    updated[role] = v
                  } else {
                    delete updated[role]
                  }
                  setKey('role_models', updated)
                }}
                width={200}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Watcher page ───────────────────────────────────────────────────────────────

function WatcherPage({
  config,
  uiPrefs,
  setKey,
  setUiPref,
  errors,
}: {
  config: DebussyConfig
  uiPrefs: UiPrefs
  setKey: (key: string, value: unknown) => Promise<void>
  setUiPref: (key: keyof UiPrefs, value: boolean) => Promise<void>
  errors: Record<string, string>
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <SettingRow
        label="Poll interval"
        description="Seconds between watcher scans for ready tasks"
        error={errors['monitor_interval']}
      >
        <NumberInput
          value={config.monitor_interval}
          min={1}
          onCommit={(n) => setKey('monitor_interval', n)}
          width={100}
        />
      </SettingRow>

      <SettingRow
        label="Auto-start watcher"
        description="Automatically start the watcher when a project is loaded"
      >
        <Toggle
          checked={uiPrefs.auto_start_watcher}
          onChange={(v) => setUiPref('auto_start_watcher', v)}
        />
      </SettingRow>

      <SettingRow
        label="Paused"
        description="Pause the watcher — no new agents will be spawned"
      >
        <Toggle
          checked={config.paused}
          onChange={(v) => setKey('paused', v)}
        />
      </SettingRow>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

const DEFAULT_UI_PREFS: UiPrefs = { auto_start_watcher: false }

export function PipelineSettings({ section }: PipelineSettingsProps) {
  const [config, setConfig] = useState<DebussyConfig | null>(null)
  const [uiPrefs, setUiPrefs] = useState<UiPrefs>(DEFAULT_UI_PREFS)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    window.debussy.config.get().then(setConfig)
    window.debussy.uiPrefs.get().then(setUiPrefs)
  }, [section])

  async function setKey(key: string, value: unknown): Promise<void> {
    const result = await window.debussy.config.set(key, value)
    if (!result.success) {
      setErrors((prev) => ({ ...prev, [key]: result.error ?? 'Failed to save' }))
    } else {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[key]
        return next
      })
      // Reload config so all inputs reflect the saved state
      const updated = await window.debussy.config.get()
      setConfig(updated)
    }
  }

  async function setUiPref(key: keyof UiPrefs, value: boolean): Promise<void> {
    const result = await window.debussy.uiPrefs.set(key, value)
    if (result.success) {
      setUiPrefs((prev) => ({ ...prev, [key]: value }))
    }
  }

  if (!config) {
    return (
      <div style={{ color: 'var(--t-text-3)', fontSize: 13, paddingTop: 8 }}>
        Loading…
      </div>
    )
  }

  return section === 'agents'
    ? <AgentsPage config={config} setKey={setKey} errors={errors} />
    : <WatcherPage config={config} uiPrefs={uiPrefs} setKey={setKey} setUiPref={setUiPref} errors={errors} />
}
