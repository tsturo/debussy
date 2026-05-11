import { useEffect, useState } from 'react'
import type { DebussyConfig } from '../../../../shared/types'

// ── Reusable field row ─────────────────────────────────────────────────────────

function SettingRow({
  label,
  description,
  children,
}: {
  label: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t-text)', marginBottom: 2 }}>
          {label}
        </div>
        <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>{description}</div>
      </div>
      {children}
    </div>
  )
}

// ── Input with Set button ──────────────────────────────────────────────────────

function ConfigInput({
  value,
  onChange,
  onSave,
  placeholder,
  saving,
  saved,
}: {
  value: string
  onChange: (v: string) => void
  onSave: () => void
  placeholder?: string
  saving: boolean
  saved: boolean
}) {
  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.currentTarget.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onSave() }}
        placeholder={placeholder}
        style={{
          flex: 1,
          padding: '6px 10px',
          fontSize: 12,
          borderRadius: 'var(--t-radius-sm)',
          border: '1px solid var(--t-border)',
          background: 'var(--t-surface)',
          color: 'var(--t-text)',
          outline: 'none',
          fontFamily: 'inherit',
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--t-purple)' }}
        onBlur={(e)  => { e.currentTarget.style.borderColor = 'var(--t-border)' }}
      />
      <button
        onClick={onSave}
        disabled={saving}
        style={{
          padding: '6px 14px',
          borderRadius: 'var(--t-radius-sm)',
          border: `1px solid ${saved ? 'var(--t-green, #22c55e)' : 'var(--t-purple)'}`,
          background: saved
            ? 'color-mix(in srgb, var(--t-green, #22c55e) 12%, transparent)'
            : 'color-mix(in srgb, var(--t-purple) 12%, transparent)',
          color: saved ? 'var(--t-green, #22c55e)' : 'var(--t-purple)',
          fontSize: 12,
          fontWeight: 600,
          cursor: saving ? 'default' : 'pointer',
          transition: 'border-color var(--t-dur-fast) var(--t-ease), background var(--t-dur-fast) var(--t-ease)',
          whiteSpace: 'nowrap',
        }}
      >
        {saved ? 'Saved' : 'Set'}
      </button>
    </div>
  )
}

// ── Git & Branches page ────────────────────────────────────────────────────────

export function GitSettings() {
  const [config, setConfig] = useState<DebussyConfig | null>(null)

  // Local input values (may differ from saved config until Set is clicked)
  const [baseBranch, setBaseBranch]     = useState('')
  const [testCommand, setTestCommand]   = useState('')

  // Per-field save feedback
  const [savingBase, setSavingBase]         = useState(false)
  const [savedBase, setSavedBase]           = useState(false)
  const [savingTest, setSavingTest]         = useState(false)
  const [savedTest, setSavedTest]           = useState(false)

  useEffect(() => {
    window.debussy.config.get().then((cfg) => {
      setConfig(cfg)
      setBaseBranch(cfg.base_branch ?? '')
      setTestCommand(cfg.test_command ?? '')
    })
  }, [])

  async function saveBaseBranch() {
    setSavingBase(true)
    const trimmed = baseBranch.trim()
    await window.debussy.config.set('base_branch', trimmed || null)
    setSavingBase(false)
    setSavedBase(true)
    setTimeout(() => setSavedBase(false), 2000)
  }

  async function saveTestCommand() {
    setSavingTest(true)
    const trimmed = testCommand.trim()
    // Clearing the field sets test_command to null (auto-detect)
    await window.debussy.config.set('test_command', trimmed || null)
    setSavingTest(false)
    setSavedTest(true)
    setTimeout(() => setSavedTest(false), 2000)
  }

  const branchPattern = config?.base_branch
    ? `feature/<task-id> branches off ${config.base_branch}`
    : 'feature/<task-id>'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>

      {/* ── Base branch ── */}
      <SettingRow
        label="Base Branch"
        description="The conductor's feature branch that agent branches merge into"
      >
        <ConfigInput
          value={baseBranch}
          onChange={setBaseBranch}
          onSave={saveBaseBranch}
          placeholder="e.g. feature/my-feature"
          saving={savingBase}
          saved={savedBase}
        />
      </SettingRow>

      {/* ── Test command ── */}
      <SettingRow
        label="Test Command"
        description="Override the auto-detected test command run by the integrator after merging"
      >
        <ConfigInput
          value={testCommand}
          onChange={setTestCommand}
          onSave={saveTestCommand}
          placeholder="auto-detect"
          saving={savingTest}
          saved={savedTest}
        />
      </SettingRow>

      {/* ── Branch naming (read-only) ── */}
      <SettingRow
        label="Branch Naming"
        description="Pattern used for developer sub-branches"
      >
        <div
          style={{
            padding: '6px 10px',
            fontSize: 12,
            borderRadius: 'var(--t-radius-sm)',
            border: '1px solid var(--t-border)',
            background: 'var(--t-surface)',
            color: 'var(--t-text-2)',
            fontFamily: 'monospace',
          }}
        >
          {branchPattern}
        </div>
      </SettingRow>

    </div>
  )
}

export default GitSettings
