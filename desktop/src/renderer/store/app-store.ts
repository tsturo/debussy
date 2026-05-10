import { create } from 'zustand'
import type { Task, AgentInfo, DebussyConfig, ConductorMessage } from '../../shared/types'

export type ThemePreference = 'system' | 'dark' | 'light'

export interface AppState {
  // Data
  tasks: Task[]
  agents: Record<string, AgentInfo>  // keyed by taskId
  config: DebussyConfig | null
  watcherRunning: boolean

  // UI state
  selectedTaskId: string | null
  conductorVisible: boolean
  sidebarCollapsed: boolean
  conductorMessages: ConductorMessage[]
  theme: ThemePreference

  // Actions
  fetchAll: () => Promise<void>
  selectTask: (id: string | null) => void
  toggleConductor: () => void
  toggleSidebar: () => void
  advanceTask: (id: string) => Promise<void>
  blockTask: (id: string) => Promise<void>
  commentOnTask: (id: string, msg: string) => Promise<void>
  addConductorMessage: (msg: ConductorMessage) => void
  setTheme: (theme: ThemePreference) => void
}

const THEME_KEY = 'debussy-theme'

function readThemeFromStorage(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  } catch {
    // localStorage may be unavailable in some contexts
  }
  return 'system'
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial data state
  tasks: [],
  agents: {},
  config: null,
  watcherRunning: false,

  // Initial UI state
  selectedTaskId: null,
  conductorVisible: true,
  sidebarCollapsed: false,
  conductorMessages: [],
  theme: readThemeFromStorage(),

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

  selectTask: (id) => set({ selectedTaskId: id }),
  toggleConductor: () => set((s) => ({ conductorVisible: !s.conductorVisible })),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  advanceTask: async (id) => {
    try {
      await window.debussy.tasks.advance(id)
    } catch (err) {
      console.error('[app-store] advanceTask failed:', err)
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

  addConductorMessage: (msg) =>
    set((s) => ({ conductorMessages: [...s.conductorMessages, msg] })),

  setTheme: (theme) => {
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // localStorage may be unavailable
    }
    set({ theme })
  },
}))
