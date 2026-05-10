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

  return { handleAddProject, handleNewWorkspace }
}
