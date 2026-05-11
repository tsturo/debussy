import { useAppStore } from '../store/app-store'

/**
 * Encapsulates workspace mutation handlers that require IPC calls (folder picker,
 * window.prompt) so they don't bloat App.tsx.
 *
 * @param showToast - Called with an error message when an operation fails.
 */
export function useWorkspaceHandlers(showToast: (msg: string) => void) {
  const addProject = useAppStore((s) => s.addProject)
  const addWorkspaceGroup = useAppStore((s) => s.addWorkspaceGroup)
  const removeProjectAction = useAppStore((s) => s.removeProject)
  const removeGroupAction = useAppStore((s) => s.removeGroup)
  const renameGroupAction = useAppStore((s) => s.renameGroup)
  const workspaceGroups = useAppStore((s) => s.workspaceGroups)

  async function handleAddProject(groupId: string) {
    try {
      const path = await window.debussy.dialog.openDirectory()
      if (!path) return  // user cancelled
      const result = await addProject(groupId, path)
      if (!result.success) {
        showToast(result.error ?? 'Could not add project')
      }
    } catch (err) {
      console.error('[useWorkspaceHandlers] handleAddProject failed:', err)
    }
  }

  async function handleNewWorkspace() {
    const name = window.prompt('Workspace name:')
    if (!name?.trim()) return
    const result = await addWorkspaceGroup(name.trim())
    if (!result.success) {
      showToast(result.error ?? 'Could not create workspace')
    }
  }

  async function handleRemoveProject(groupId: string, projectPath: string) {
    const group = workspaceGroups.find((g) => g.id === groupId)
    const project = group?.projects.find((p) => p.path === projectPath)
    const name = project?.name ?? projectPath
    const ok = window.confirm(
      `Remove "${name}" from workspace? The project files will not be deleted.`
    )
    if (!ok) return
    const result = await removeProjectAction(groupId, projectPath)
    if (!result.success) {
      showToast(result.error ?? 'Could not remove project')
    }
  }

  async function handleRemoveGroup(groupId: string) {
    const group = workspaceGroups.find((g) => g.id === groupId)
    const name = group?.name ?? 'this workspace'
    const ok = window.confirm(
      `Delete workspace "${name}"? Projects will not be deleted from disk.`
    )
    if (!ok) return
    const result = await removeGroupAction(groupId)
    if (!result.success) {
      showToast(result.error ?? 'Could not delete workspace')
    }
  }

  async function handleRenameGroup(groupId: string, newName: string) {
    const result = await renameGroupAction(groupId, newName)
    if (!result.success) {
      showToast(result.error ?? 'Could not rename workspace')
    }
  }

  return {
    handleAddProject,
    handleNewWorkspace,
    handleRemoveProject,
    handleRemoveGroup,
    handleRenameGroup,
  }
}
