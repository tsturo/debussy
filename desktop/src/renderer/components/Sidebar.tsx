export interface SidebarProject {
  name: string
  isActive: boolean
  agentCount: number
  status: 'active' | 'running' | 'idle'
}

export interface SidebarProps {
  workspaceName: string
  workspaceInitial: string
  projects: SidebarProject[]
  collapsed: boolean
  onToggle?: () => void
  onProjectSelect: (name: string) => void
  onSettingsClick: () => void
  onAddProject: () => void
}

// Status dot colors per project status (using CSS variables from globals.css)
const STATUS_DOT_COLOR: Record<SidebarProject['status'], string> = {
  active:  'var(--t-teal)',           // teal — active watcher
  running: 'var(--t-warn)',           // amber — has agents
  idle:    'var(--t-text-3)',         // gray at 40% (applied via opacity)
}

function GradientAvatar({ initial }: { initial: string }) {
  return (
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: 9,
        background: 'var(--t-gradient)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        fontWeight: 700,
        fontSize: 13,
        color: 'white',
        letterSpacing: '-0.01em',
        userSelect: 'none',
      }}
    >
      {initial}
    </div>
  )
}

function ChevronDownIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-text-3)', flexShrink: 0 }}
    >
      <path
        d="M2 4l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function GearIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-text-3)', flexShrink: 0 }}
    >
      <path
        d="M7 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11.33 7c0-.19-.01-.37-.04-.55l1.2-.93a.3.3 0 0 0 .07-.38l-1.13-1.96a.3.3 0 0 0-.36-.13l-1.41.57a4.1 4.1 0 0 0-.95-.55l-.21-1.5A.3.3 0 0 0 8.2 1H5.8a.3.3 0 0 0-.3.26l-.21 1.5c-.34.14-.66.32-.95.55L2.93 2.74a.3.3 0 0 0-.36.13L1.44 4.83a.3.3 0 0 0 .07.38l1.2.93A3.3 3.3 0 0 0 2.67 7c0 .19.01.37.04.55l-1.2.93a.3.3 0 0 0-.07.38l1.13 1.96c.08.14.24.2.36.13l1.41-.57c.29.23.61.41.95.55l.21 1.5c.04.15.17.26.3.26h2.4c.13 0 .26-.11.3-.26l.21-1.5c.34-.14.66-.32.95-.55l1.41.57c.12.07.28.01.36-.13l1.13-1.96a.3.3 0 0 0-.07-.38l-1.2-.93c.03-.18.04-.36.04-.55Z"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function PlusPurpleIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-purple)', flexShrink: 0 }}
    >
      <path
        d="M6 1v10M1 6h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

function ProjectRow({
  project,
  onSelect,
}: {
  project: SidebarProject
  onSelect: () => void
}) {
  const isIdle = project.status === 'idle'

  return (
    <button
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        width: '100%',
        padding: '6px 8px',
        borderRadius: 9,
        border: 'none',
        cursor: 'pointer',
        background: project.isActive ? 'var(--t-surface)' : 'transparent',
        boxShadow: project.isActive
          ? '0 1px 3px rgba(0,0,0,0.08)'
          : 'none',
        textAlign: 'left',
        transition: 'background var(--t-dur-fast) var(--t-ease)',
      }}
    >
      {/* Status dot */}
      <div
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          flexShrink: 0,
          backgroundColor: STATUS_DOT_COLOR[project.status],
          opacity: isIdle ? 0.4 : 1,
        }}
      />

      {/* Project name */}
      <span
        style={{
          flex: 1,
          fontSize: 12,
          fontWeight: project.isActive ? 500 : 400,
          color: project.isActive ? 'var(--t-text)' : 'var(--t-text-3)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {project.name}
      </span>

      {/* Agent count badge */}
      {project.agentCount > 0 && (
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: 'var(--t-purple)',
            background: 'color-mix(in srgb, var(--t-purple) 12%, transparent)',
            borderRadius: 100,
            padding: '1px 6px',
            flexShrink: 0,
            lineHeight: '16px',
          }}
        >
          {project.agentCount}
        </span>
      )}
    </button>
  )
}

export function Sidebar({
  workspaceName,
  workspaceInitial,
  projects,
  collapsed,
  onToggle,
  onProjectSelect,
  onSettingsClick,
  onAddProject,
}: SidebarProps) {
  const width = collapsed ? 48 : 248

  return (
    <div
      style={{
        width,
        minWidth: width,
        maxWidth: width,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--t-bg)',
        borderRight: '1px solid var(--t-border)',
        overflow: 'hidden',
        transition: `width var(--t-dur-base) var(--t-ease), min-width var(--t-dur-base) var(--t-ease)`,
        boxSizing: 'border-box',
      }}
    >
      {/* ── Workspace header ─────────────────────────────────────────── */}
      <button
        onClick={collapsed ? onToggle : undefined /* onWorkspaceClick — future */}
        aria-label={collapsed ? 'Expand sidebar' : undefined}
        title={collapsed ? 'Expand sidebar' : undefined}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: collapsed ? '10px 10px' : '10px 12px',
          border: 'none',
          background: 'transparent',
          cursor: collapsed ? 'pointer' : 'default',
          flexShrink: 0,
          width: '100%',
          textAlign: 'left',
          overflow: 'hidden',
        }}
      >
        <GradientAvatar initial={workspaceInitial} />

        {!collapsed && (
          <>
            <span
              style={{
                flex: 1,
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--t-text)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {workspaceName}
            </span>
            <ChevronDownIcon />
          </>
        )}
      </button>

      {/* ── Project list (scrollable) ────────────────────────────────── */}
      {!collapsed && (
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: '4px 8px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          {/* Section label */}
          <div
            style={{
              fontSize: 9,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.10em',
              color: 'var(--t-text-3)',
              padding: '6px 8px 4px',
            }}
          >
            Projects
          </div>

          {/* Project rows */}
          {projects.map((project) => (
            <ProjectRow
              key={project.name}
              project={project}
              onSelect={() => onProjectSelect(project.name)}
            />
          ))}

          {/* Add project link */}
          <button
            onClick={onAddProject}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 8px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              borderRadius: 9,
              width: '100%',
              textAlign: 'left',
              marginTop: 2,
            }}
          >
            <PlusPurpleIcon />
            <span
              style={{
                fontSize: 12,
                color: 'var(--t-purple)',
                fontWeight: 500,
              }}
            >
              Add project
            </span>
          </button>
        </div>
      )}

      {/* Spacer in collapsed mode */}
      {collapsed && <div style={{ flex: 1 }} />}

      {/* ── Footer ──────────────────────────────────────────────────── */}
      {!collapsed && (
        <div
          style={{
            borderTop: '1px solid var(--t-border)',
            padding: '8px',
            flexShrink: 0,
          }}
        >
          <button
            onClick={onSettingsClick}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '6px 8px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              borderRadius: 9,
              textAlign: 'left',
            }}
          >
            <GearIcon />
            <span
              style={{
                fontSize: 12,
                color: 'var(--t-text-3)',
              }}
            >
              Settings
            </span>
          </button>
        </div>
      )}
    </div>
  )
}

export default Sidebar
