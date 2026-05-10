export interface HeaderProps {
  projectName: string
  agentCount: number
  maxAgents: number
  blockedCount: number
  onSearchClick: () => void
  onNewTaskClick: () => void
}

export function Header({
  projectName,
  agentCount,
  maxAgents,
  blockedCount,
  onSearchClick,
  onNewTaskClick,
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
            borderRadius: '9px',
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

        <button
          onClick={onNewTaskClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '5px 12px',
            background: 'var(--t-gradient)',
            border: 'none',
            borderRadius: '9px',
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
        borderRadius: '100px',
        fontSize: '11px',
        color: 'var(--t-text-2)',
        background: 'rgba(108, 92, 231, 0.06)',
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
        borderRadius: '100px',
        fontSize: '11px',
        color: 'var(--t-error)',
        background: 'rgba(217, 112, 112, 0.08)',
      }}
    >
      {blockedCount} blocked
    </span>
  )
}
