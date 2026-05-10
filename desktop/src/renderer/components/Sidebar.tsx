import { useState, useRef, useEffect } from 'react'
import type { WorkspaceGroupData } from '../store/app-store'
import { WorkspaceDropdown } from './WorkspaceDropdown'
import { GradientAvatar, ChevronDownIcon, GearIcon, PlusPurpleIcon } from './icons'

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
  onRemoveProject: (groupId: string, path: string) => void
  onNewWorkspace: () => void
  onRenameGroup: (groupId: string, newName: string) => void
  onRemoveGroup: (groupId: string) => void
  onSettingsClick: () => void
}

// ── Project row ──────────────────────────────────────────────────────────────

function ProjectRow({
  name,
  isActive,
  onClick,
  onRemove,
}: {
  name: string
  isActive: boolean
  onClick: () => void
  onRemove: () => void
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        onClick={onClick}
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: hovered ? '6px 24px 6px 8px' : '6px 8px',
          borderRadius: 9,
          border: 'none',
          cursor: 'pointer',
          background: isActive ? 'var(--t-surface)' : 'transparent',
          boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
          textAlign: 'left',
          transition: 'background var(--t-dur-fast) var(--t-ease)',
          minWidth: 0,
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

      {/* Remove button — shown on hover */}
      {hovered && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          title="Remove from workspace"
          aria-label={`Remove ${name} from workspace`}
          style={{
            position: 'absolute',
            right: 6,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 16,
            height: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            borderRadius: 4,
            color: 'var(--t-text-3)',
            fontSize: 14,
            lineHeight: 1,
            padding: 0,
            opacity: 0.6,
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.6' }}
        >
          ×
        </button>
      )}
    </div>
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
  onRemoveProject,
  onNewWorkspace,
  onRenameGroup,
  onRemoveGroup,
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
          onRenameGroup={(groupId, newName) => {
            onRenameGroup(groupId, newName)
          }}
          onRemoveGroup={(groupId) => {
            onRemoveGroup(groupId)
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
              onRemove={() => onRemoveProject(activeGroupId ?? '', project.path)}
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
