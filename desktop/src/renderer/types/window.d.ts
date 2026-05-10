import type { Task, Dependency, LogEntry, WatcherState, DebussyConfig } from '../../shared/types'

export interface TaskDetail extends Task {
  deps: Dependency[]
  log: LogEntry[]
}

interface WorkspaceProject {
  path: string
  name: string
}

interface WorkspaceGroup {
  id: string
  name: string
  iconLetter: string
  projects: WorkspaceProject[]
}

interface WorkspaceData {
  groups: WorkspaceGroup[]
  activeGroupId: string | null
  activeProjectPath: string | null
}

interface DebussyAPI {
  tasks: {
    list:    ()                            => Promise<Task[]>
    get:     (id: string)                  => Promise<TaskDetail | null>
    advance: (id: string)                  => Promise<{ success: boolean }>
    block:   (id: string)                  => Promise<{ success: boolean }>
    comment: (id: string, msg: string)     => Promise<{ success: boolean }>
    create:  (title: string, desc: string) => Promise<{ success: boolean }>
  }
  agents: {
    list:              ()                                                           => Promise<WatcherState>
    startLog:          (agentName: string)                                          => void
    stopLog:           (agentName: string)                                          => void
    onLogLine:         (callback: (data: { agent: string; line: string }) => void)  => void
    removeLogListener: ()                                                           => void
  }
  config: {
    get: () => Promise<DebussyConfig>
    set: (key: string, value: string | number | boolean | null) => Promise<{ success: boolean; error?: string }>
  }
  watcher: {
    status: () => Promise<{ running: boolean }>
    start:  () => Promise<{ success: boolean; alreadyRunning?: boolean }>
    stop:   () => Promise<{ success: boolean }>
  }
  conductor: {
    send:            (message: string)                    => Promise<{ success: boolean }>
    cancel:          ()                                   => void
    newSession:      ()                                   => Promise<{ success: boolean }>
    onChunk:         (callback: (chunk: string) => void)  => void
    onDone:          (callback: () => void)               => void
    removeListeners: ()                                   => void
  }
  workspace: {
    list:          ()                                                   => Promise<WorkspaceData>
    addGroup:      (name: string, iconLetter: string)                   => Promise<{ success: boolean; group?: WorkspaceGroup; error?: string }>
    addProject:    (groupId: string, projectPath: string)               => Promise<{ success: boolean; error?: string }>
    removeProject: (groupId: string, projectPath: string)               => Promise<{ success: boolean; error?: string }>
    setActive:     (groupId: string, projectPath: string)               => Promise<{ success: boolean; error?: string }>
  }
  dialog: {
    openDirectory: () => Promise<string | null>
  }
  app: {
    info: () => Promise<{
      appVersion: string
      electronVersion: string
      nodeVersion: string
      chromeVersion: string
    }>
  }
  shell: {
    openExternal: (url: string) => Promise<{ success: boolean; error?: string }>
  }
}

declare global {
  interface Window {
    debussy: DebussyAPI
  }
}

export {}
