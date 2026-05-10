import { useState, useRef, useEffect } from 'react'
import type { WorkspaceGroupData } from '../store/app-store'

export type { WorkspaceGroupData }

export interface SidebarProps {
  workspaceGroups: WorkspaceGroupData[]
  activeGroupId: string | null
  activeProjectPath: string | null
  collapsed: boolean
  onToggle?: () => void
  onGroupSelect: (groupId: string) => void
  onProjectSelect: (groupId: string, path: string) => void
  onAddProject: (groupId: string) => void
  onNewWorkspace: () => void
  onSettingsClick: () => void
}

// ── Icon components ──────────────────────────────────────────────────────────

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

function ChevronDownIcon({ open }: { open?: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        color: 'var(--t-text-3)',
        flexShrink: 0,
        transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
        transition: 'transform 150ms ease',
      }}
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

function CheckIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ color: 'var(--t-teal)', flexShrink: 0 }}
    >
      <path
        d="M2 6l3 3 5-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ── Workspace switcher dropdown ──────────────────────────────────────────────

interface WorkspaceDropdownProps {
  groups: WorkspaceGroupData[]
  activeGroupId: string | null
  anchorRect: DOMRect | null
  onGroupSelect: (groupId: string) => void
  onNewWorkspace: () => void
  onClose: () => void
}

function WorkspaceDropdown({
  groups,
  activeGroupId,
  anchorRect,
  onGroupSelect,
  onNewWorkspace,
  onClose,
}: WorkspaceDropdownProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleMousedown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    function handleKeydown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleMousedown)
    document.addEventListener('keydown', handleKeydown)
    return () => {
      document.removeEventListener('mousedown', handleMousedown)
      document.removeEventListener('keydown', handleKeydown)
    }
  }, [onClose])

  const top = anchorRect ? anchorRect.bottom + 4 : 48
  const left = anchorRect ? anchorRect.left : 8

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top,
        left,
        width: 232,
        zIndex: 200,
        background: 'var(--t-surface)',
        border: '1px solid var(--t-border)',
        borderRadius: 10,
        boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
        overflow: 'hidden',
        padding: '4px 0',
      }}
    >
      {/* Group list */}
      {groups.map((group) => (
        <button
          key={group.id}
          onClick={() => { onGroupSelect(group.id); onClose() }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            width: '100%',
            padding: '7px 10px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            textAlign: 'left',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'var(--t-bg)'
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'transparent'
          }}
        >
          <GradientAvatar initial={group.iconLetter} />
          <span
            style={{
              flex: 1,
              fontSize: 13,
              fontWeight: group.id === activeGroupId ? 600 : 400,
              color: 'var(--t-text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {group.name}
          </span>
          {group.id === activeGroupId && <CheckIcon />}
        </button>
      ))}

      {/* Divider */}
      <div style={{ height: 1, background: 'var(--t-border)', margin: '4px 0' }} />

      {/* New Workspace */}
      <button
        onClick={() => { onNewWorkspace(); onClose() }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          padding: '7px 10px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.background = 'var(--t-bg)'
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.background = 'transparent'
        }}
      >
        <PlusPurpleIcon />
        <span style={{ fontSize: 13, color: 'var(--t-purple)', fontWeight: 500 }}>
          New Workspace
        </span>
      </button>
    </div>
  )
}

// ── Project row ──────────────────────────────────────────────────────────────

function ProjectRow({
  name,
  isActive,
  onClick,
}: {
  name: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        width: '100%',
        padding: '6px 8px',
        borderRadius: 9,
        border: 'none',
        cursor: 'pointer',
        background: isActive ? 'var(--t-surface)' : 'transparent',
        boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
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
          backgroundColor: isActive ? 'var(--t-teal)' : 'var(--t-text-3)',
          opacity: isActive ? 1 : 0.4,
        }}
      />

      {/* Project name */}
      <span
        style={{
          flex: 1,
          fontSize: 12,
          fontWeight: isActive ? 500 : 400,
          color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {name}
      </span>
    </button>
  )
}

// ── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar({
  workspaceGroups,
  activeGroupId,
  activeProjectPath,
  collapsed,
  onToggle,
  onGroupSelect,
  onProjectSelect,
  onAddProject,
  onNewWorkspace,
  onSettingsClick,
}: SidebarProps) {
  const width = collapsed ? 48 : 248
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  // Derive active group's projects
  const activeGroup = workspaceGroups.find((g) => g.id === activeGroupId) ?? null
  const projects = activeGroup?.projects ?? []

  // Workspace display: show first group name or placeholder
  const displayGroup = activeGroup ?? workspaceGroups[0] ?? null
  const workspaceName = displayGroup?.name ?? 'Workspace'
  const workspaceInitial = displayGroup?.iconLetter ?? 'W'

  function handleWorkspaceClick() {
    if (collapsed) {
      onToggle?.()
      return
    }
    if (triggerRef.current) {
      setAnchorRect(triggerRef.current.getBoundingClientRect())
    }
    setDropdownOpen((open) => !open)
  }

  // Close dropdown when sidebar collapses
  useEffect(() => {
    if (collapsed) setDropdownOpen(false)
  }, [collapsed])

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
      {/* ── Workspace header ─────────────────────────────────────────────── */}
      <button
        ref={triggerRef}
        onClick={handleWorkspaceClick}
        aria-label={collapsed ? 'Expand sidebar' : 'Switch workspace'}
        title={collapsed ? 'Expand sidebar' : 'Switch workspace'}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: collapsed ? '10px 10px' : '10px 12px',
          border: 'none',
          background: dropdownOpen ? 'color-mix(in srgb, var(--t-surface) 60%, transparent)' : 'transparent',
          cursor: 'pointer',
          flexShrink: 0,
          width: '100%',
          textAlign: 'left',
          overflow: 'hidden',
          borderRadius: 0,
          transition: 'background var(--t-dur-fast) var(--t-ease)',
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
            <ChevronDownIcon open={dropdownOpen} />
          </>
        )}
      </button>

      {/* ── Workspace switcher dropdown ──────────────────────────────────── */}
      {dropdownOpen && !collapsed && (
        <WorkspaceDropdown
          groups={workspaceGroups}
          activeGroupId={activeGroupId}
          anchorRect={anchorRect}
          onGroupSelect={(id) => {
            onGroupSelect(id)
            setDropdownOpen(false)
          }}
          onNewWorkspace={() => {
            onNewWorkspace()
            setDropdownOpen(false)
          }}
          onClose={() => setDropdownOpen(false)}
        />
      )}

      {/* ── Project list (scrollable) ────────────────────────────────────── */}
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
              key={project.path}
              name={project.name}
              isActive={project.path === activeProjectPath}
              onClick={() => onProjectSelect(activeGroupId ?? '', project.path)}
            />
          ))}

          {/* Add project link */}
          <button
            onClick={() => onAddProject(activeGroupId ?? '')}
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

      {/* ── Footer ──────────────────────────────────────────────────────── */}
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
