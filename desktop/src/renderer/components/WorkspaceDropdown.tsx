import { useRef, useEffect, useState, useCallback } from 'react'
import type { WorkspaceGroupData } from '../store/app-store'
import { GradientAvatar, PlusPurpleIcon, CheckIcon, PencilIcon, TrashIcon } from './icons'

export interface WorkspaceDropdownProps {
  groups: WorkspaceGroupData[]
  activeGroupId: string | null
  anchorRect: DOMRect | null
  onGroupSelect: (groupId: string) => void
  onNewWorkspace: () => void
  onRenameGroup: (groupId: string, newName: string) => void
  onRemoveGroup: (groupId: string) => void
  onClose: () => void
}

export function WorkspaceDropdown({
  groups,
  activeGroupId,
  anchorRect,
  onGroupSelect,
  onNewWorkspace,
  onRenameGroup,
  onRemoveGroup,
  onClose,
}: WorkspaceDropdownProps) {
  const ref = useRef<HTMLDivElement>(null)
  const renameInputRef = useRef<HTMLInputElement>(null)

  const [renamingGroupId, setRenamingGroupId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [hoveredGroupId, setHoveredGroupId] = useState<string | null>(null)

  useEffect(() => {
    function handleMousedown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    function handleKeydown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (renamingGroupId) {
          setRenamingGroupId(null)
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('mousedown', handleMousedown)
    document.addEventListener('keydown', handleKeydown)
    return () => {
      document.removeEventListener('mousedown', handleMousedown)
      document.removeEventListener('keydown', handleKeydown)
    }
  }, [onClose, renamingGroupId])

  // Focus the rename input when it appears
  useEffect(() => {
    if (renamingGroupId && renameInputRef.current) {
      renameInputRef.current.focus()
      renameInputRef.current.select()
    }
  }, [renamingGroupId])

  const startRename = useCallback((group: WorkspaceGroupData, e: React.MouseEvent) => {
    e.stopPropagation()
    setRenamingGroupId(group.id)
    setRenameValue(group.name)
  }, [])

  const commitRename = useCallback(() => {
    if (renamingGroupId && renameValue.trim()) {
      onRenameGroup(renamingGroupId, renameValue.trim())
    }
    setRenamingGroupId(null)
  }, [renamingGroupId, renameValue, onRenameGroup])

  const cancelRename = useCallback(() => {
    setRenamingGroupId(null)
  }, [])

  const handleDeleteGroup = useCallback((group: WorkspaceGroupData, e: React.MouseEvent) => {
    e.stopPropagation()
    const ok = window.confirm(
      `Delete workspace "${group.name}"? Projects will not be deleted from disk.`
    )
    if (ok) {
      onRemoveGroup(group.id)
      onClose()
    }
  }, [onRemoveGroup, onClose])

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
        <div
          key={group.id}
          style={{ position: 'relative' }}
          onMouseEnter={() => setHoveredGroupId(group.id)}
          onMouseLeave={() => setHoveredGroupId(null)}
        >
          {renamingGroupId === group.id ? (
            /* ── Inline rename input ── */
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '7px 10px',
              }}
            >
              <GradientAvatar initial={group.iconLetter} />
              <input
                ref={renameInputRef}
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); commitRename() }
                  if (e.key === 'Escape') { e.preventDefault(); cancelRename() }
                }}
                onBlur={commitRename}
                style={{
                  flex: 1,
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'var(--t-text)',
                  background: 'var(--t-bg)',
                  border: '1px solid var(--t-purple)',
                  borderRadius: 5,
                  padding: '2px 6px',
                  outline: 'none',
                  minWidth: 0,
                }}
              />
            </div>
          ) : (
            /* ── Normal group row ── */
            <button
              onClick={() => onGroupSelect(group.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '7px 10px',
                border: 'none',
                background: hoveredGroupId === group.id ? 'var(--t-bg)' : 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
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
              {group.id === activeGroupId && hoveredGroupId !== group.id && <CheckIcon />}

              {/* Action icons — visible on hover */}
              {hoveredGroupId === group.id && (
                <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                  <button
                    onClick={(e) => startRename(group, e)}
                    title="Rename workspace"
                    style={{
                      padding: '2px',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      borderRadius: 4,
                      opacity: 0.7,
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.7' }}
                  >
                    <PencilIcon />
                  </button>
                  <button
                    onClick={(e) => handleDeleteGroup(group, e)}
                    title="Delete workspace"
                    style={{
                      padding: '2px',
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      borderRadius: 4,
                      opacity: 0.7,
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.7' }}
                  >
                    <TrashIcon />
                  </button>
                </div>
              )}
            </button>
          )}
        </div>
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
