import { create } from 'zustand'
import type { Task, AgentInfo, DebussyConfig, ConductorMessage } from '../../shared/types'

export type Theme = 'system' | 'dark' | 'light'
export type ConductorDefaultVisibility = 'always' | 'auto' | 'hidden'

export interface WorkspaceProjectData {
  path: string
  name: string
}

export interface WorkspaceGroupData {
  id: string
  name: string
  iconLetter: string
  projects: WorkspaceProjectData[]
}

export interface AppState {
  // Data
  tasks: Task[]
  agents: Record<string, AgentInfo>  // keyed by taskId
  config: DebussyConfig | null
  watcherRunning: boolean

  // Workspace
  workspaceGroups: WorkspaceGroupData[]
  activeGroupId: string | null
  activeProjectPath: string | null

  // UI state
  selectedTaskId: string | null
  sidebarCollapsed: boolean
  conductorMessages: ConductorMessage[]
  conductorStreaming: boolean

  // Settings
  theme: Theme
  conductorDefaultVisibility: ConductorDefaultVisibility

  // Actions
  fetchAll: () => Promise<void>
  fetchWorkspaces: () => Promise<void>
  selectTask: (id: string | null) => void
  toggleSidebar: () => void
  advanceTask: (id: string) => Promise<void>
  moveTask: (id: string, fromStage: import('../../shared/types').Stage, toStage: import('../../shared/types').Stage, isBlocked: boolean) => Promise<void>
  blockTask: (id: string) => Promise<void>
  commentOnTask: (id: string, msg: string) => Promise<void>
  startWatcher: () => Promise<{ alreadyRunning?: boolean }>
  stopWatcher: () => Promise<void>
  addConductorMessage: (msg: ConductorMessage) => void
  clearConductorMessages: () => void
  setConductorStreaming: (val: boolean) => void
  setTheme: (theme: Theme) => void
  setConductorDefaultVisibility: (v: ConductorDefaultVisibility) => void
  setActiveGroup: (id: string) => Promise<void>
  setActiveProject: (groupId: string, path: string) => Promise<void>
  addProject: (groupId: string, path: string) => Promise<{ success: boolean; error?: string }>
  addWorkspaceGroup: (name: string) => Promise<{ success: boolean; error?: string }>
  removeProject: (groupId: string, path: string) => Promise<{ success: boolean; error?: string }>
  removeGroup: (groupId: string) => Promise<{ success: boolean; error?: string }>
  renameGroup: (groupId: string, newName: string) => Promise<{ success: boolean; error?: string }>
}

const THEME_KEY = 'debussy-theme'

function readThemeFromStorage(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  } catch {
    // localStorage may be unavailable in some contexts
  }
  return 'dark'
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial data state
  tasks: [],
  agents: {},
  config: null,
  watcherRunning: false,

  // Workspace state
  workspaceGroups: [],
  activeGroupId: null,
  activeProjectPath: null,

  // Initial UI state
  selectedTaskId: null,
  sidebarCollapsed: false,
  conductorMessages: [],
  conductorStreaming: false,

  // Settings defaults
  theme: readThemeFromStorage(),
  conductorDefaultVisibility: 'auto',

  // Fetch all data via IPC
  fetchAll: async () => {
    try {
      const api = window.debussy
      const [tasks, watcherState, config, watcherStatus] = await Promise.allSettled([
        api.tasks.list(),
        api.agents.list(),
        api.config.get(),
        api.watcher.status(),
      ])

      set({
        tasks: tasks.status === 'fulfilled' ? tasks.value : get().tasks,
        agents: watcherState.status === 'fulfilled' ? watcherState.value : get().agents,
        config: config.status === 'fulfilled' ? config.value : get().config,
        watcherRunning:
          watcherStatus.status === 'fulfilled'
            ? watcherStatus.value.running
            : get().watcherRunning,
      })
    } catch {
      // Don't crash — keep showing existing state
    }
  },

  fetchWorkspaces: async () => {
    try {
      const data = await window.debussy.workspace.list()
      set({
        workspaceGroups: data.groups as WorkspaceGroupData[],
        activeGroupId: data.activeGroupId,
        activeProjectPath: data.activeProjectPath,
      })
    } catch {
      // keep existing state on failure
    }
  },

  setActiveGroup: async (id: string) => {
    // Update local state immediately for a snappy UI
    set({ activeGroupId: id })

    // Persist to backend: switch to the first project of the selected group
    const { workspaceGroups } = get()
    const group = workspaceGroups.find((g) => g.id === id)
    const firstProject = group?.projects[0]
    if (firstProject) {
      try {
        await window.debussy.workspace.setActive(id, firstProject.path)
        set({ activeProjectPath: firstProject.path })
        await get().fetchAll()
      } catch (err) {
        console.error('[app-store] setActiveGroup persist failed:', err)
      }
    }
  },

  setActiveProject: async (groupId: string, path: string) => {
    try {
      await window.debussy.workspace.setActive(groupId, path)
      set({ activeGroupId: groupId, activeProjectPath: path })
      await get().fetchAll()
    } catch (err) {
      console.error('[app-store] setActiveProject failed:', err)
    }
  },

  addProject: async (groupId: string, path: string) => {
    try {
      const result = await window.debussy.workspace.addProject(groupId, path)
      if (result.success) {
        await get().fetchWorkspaces()
      }
      return result
    } catch (err) {
      console.error('[app-store] addProject failed:', err)
      return { success: false, error: String(err) }
    }
  },

  addWorkspaceGroup: async (name: string) => {
    try {
      const iconLetter = name.charAt(0).toUpperCase()
      const result = await window.debussy.workspace.addGroup(name, iconLetter)
      if (result.success) {
        await get().fetchWorkspaces()
      }
      return { success: result.success, error: result.error }
    } catch (err) {
      console.error('[app-store] addWorkspaceGroup failed:', err)
      return { success: false, error: String(err) }
    }
  },

  removeProject: async (groupId: string, path: string) => {
    try {
      const result = await window.debussy.workspace.removeProject(groupId, path)
      if (result.success) {
        await get().fetchWorkspaces()
      }
      return result
    } catch (err) {
      console.error('[app-store] removeProject failed:', err)
      return { success: false, error: String(err) }
    }
  },

  removeGroup: async (groupId: string) => {
    try {
      const result = await window.debussy.workspace.removeGroup(groupId)
      if (result.success) {
        await get().fetchWorkspaces()
      }
      return result
    } catch (err) {
      console.error('[app-store] removeGroup failed:', err)
      return { success: false, error: String(err) }
    }
  },

  renameGroup: async (groupId: string, newName: string) => {
    try {
      const result = await window.debussy.workspace.renameGroup(groupId, newName)
      if (result.success) {
        await get().fetchWorkspaces()
      }
      return result
    } catch (err) {
      console.error('[app-store] renameGroup failed:', err)
      return { success: false, error: String(err) }
    }
  },

  selectTask: (id) => set({ selectedTaskId: id }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  advanceTask: async (id) => {
    try {
      await window.debussy.tasks.advance(id)
    } catch (err) {
      console.error('[app-store] advanceTask failed:', err)
    }
    await get().fetchAll()
  },

  moveTask: async (id, _fromStage, toStage, isBlocked) => {
    try {
      if (isBlocked && toStage === 'development') {
        // Unblock first, then move to development
        await window.debussy.tasks.release(id)
      }
      await window.debussy.tasks.advanceTo(id, toStage)
    } catch (err) {
      console.error('[app-store] moveTask failed:', err)
    }
    await get().fetchAll()
  },

  blockTask: async (id) => {
    try {
      await window.debussy.tasks.block(id)
    } catch (err) {
      console.error('[app-store] blockTask failed:', err)
    }
    await get().fetchAll()
  },

  commentOnTask: async (id, msg) => {
    try {
      await window.debussy.tasks.comment(id, msg)
    } catch (err) {
      console.error('[app-store] commentOnTask failed:', err)
    }
    await get().fetchAll()
  },

  startWatcher: async () => {
    try {
      const result = await window.debussy.watcher.start()
      await get().fetchAll()
      return { alreadyRunning: result.alreadyRunning }
    } catch (err) {
      console.error('[app-store] startWatcher failed:', err)
      return {}
    }
  },

  stopWatcher: async () => {
    try {
      await window.debussy.watcher.stop()
    } catch (err) {
      console.error('[app-store] stopWatcher failed:', err)
    }
    await get().fetchAll()
  },

  addConductorMessage: (msg) =>
    set((s) => ({ conductorMessages: [...s.conductorMessages, msg] })),

  clearConductorMessages: () => set({ conductorMessages: [] }),

  setConductorStreaming: (val) => set({ conductorStreaming: val }),

  setTheme: (theme) => {
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // localStorage may be unavailable
    }
    set({ theme })
  },

  setConductorDefaultVisibility: (conductorDefaultVisibility) =>
    set({ conductorDefaultVisibility }),
}))
