export interface HeaderProps {
  projectName: string
  agentCount: number
  maxAgents: number
  blockedCount: number
  conductorVisible: boolean
  onSearchClick: () => void
  onNewTaskClick: () => void
  onToggleConductor: () => void
}

export function Header({
  projectName,
  agentCount,
  maxAgents,
  blockedCount,
  conductorVisible,
  onSearchClick,
  onNewTaskClick,
  onToggleConductor,
}: HeaderProps) {
  return (
    <header
      style={{
        height: '52px',
        background: 'var(--t-surface)',
        borderBottom: '1px solid var(--t-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '16px',
        flexShrink: 0,
      }}
    >
      {/* Left: project name */}
      <span
        style={{
          fontSize: '15px',
          fontWeight: 600,
          color: 'var(--t-text)',
          whiteSpace: 'nowrap',
        }}
      >
        {projectName}
      </span>

      {/* Center: status pills */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          flex: 1,
          justifyContent: 'center',
        }}
      >
        <AgentPill agentCount={agentCount} maxAgents={maxAgents} />
        {blockedCount > 0 && <BlockedPill blockedCount={blockedCount} />}
      </div>

      {/* Right: action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          onClick={onSearchClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            background: 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderRadius: 'var(--t-radius-sm)',
            cursor: 'pointer',
            fontSize: '13px',
            color: 'var(--t-text-3)',
          }}
        >
          Search
          <kbd
            style={{
              fontSize: '11px',
              color: 'var(--t-text-3)',
              fontFamily: 'inherit',
            }}
          >
            ⌘K
          </kbd>
        </button>

        {/* Conductor toggle button — always visible */}
        <button
          onClick={onToggleConductor}
          title="Toggle Conductor (⌘\)"
          aria-label="Toggle Conductor"
          aria-pressed={conductorVisible}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 32,
            height: 32,
            background: conductorVisible ? 'rgba(108, 92, 231, 0.12)' : 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderRadius: 'var(--t-radius-sm)',
            cursor: 'pointer',
            color: conductorVisible ? 'var(--t-purple)' : 'var(--t-text-3)',
            flexShrink: 0,
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>

        <button
          onClick={onNewTaskClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '5px 12px',
            background: 'var(--t-gradient)',
            border: 'none',
            borderRadius: 'var(--t-radius-sm)',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 600,
            color: '#ffffff',
            whiteSpace: 'nowrap',
          }}
        >
          + New Task
        </button>
      </div>
    </header>
  )
}

function AgentPill({
  agentCount,
  maxAgents,
}: {
  agentCount: number
  maxAgents: number
}) {
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: 'var(--t-radius-pill)',
        fontSize: '11px',
        color: 'var(--t-text-2)',
        background: 'var(--t-agent-pill-bg)',
      }}
    >
      {agentCount}/{maxAgents} agents
    </span>
  )
}

function BlockedPill({ blockedCount }: { blockedCount: number }) {
  return (
    <span
      style={{
        padding: '3px 10px',
        borderRadius: 'var(--t-radius-pill)',
        fontSize: '11px',
        color: 'var(--t-error)',
        background: 'var(--t-blocked-pill-bg)',
      }}
    >
      {blockedCount} blocked
    </span>
  )
}
