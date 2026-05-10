import { useRef, useEffect } from 'react'
import type { WorkspaceGroupData } from '../store/app-store'
import { GradientAvatar, PlusPurpleIcon, CheckIcon } from './icons'

export interface WorkspaceDropdownProps {
  groups: WorkspaceGroupData[]
  activeGroupId: string | null
  anchorRect: DOMRect | null
  onGroupSelect: (groupId: string) => void
  onNewWorkspace: () => void
  onClose: () => void
}

export function WorkspaceDropdown({
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
          onClick={() => onGroupSelect(group.id)}
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
        onClick={onNewWorkspace}
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
