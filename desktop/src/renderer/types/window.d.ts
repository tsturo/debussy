import type { Task, Dependency, LogEntry, WatcherState, DebussyConfig } from '../../shared/types'

export interface TaskDetail extends Task {
  deps: Dependency[]
  log: LogEntry[]
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
  }
  watcher: {
    status: () => Promise<{ running: boolean }>
    start:  () => Promise<{ success: boolean; alreadyRunning?: boolean }>
    stop:   () => Promise<{ success: boolean }>
  }
  conductor: {
    send:            (message: string)                    => Promise<{ success: boolean }>
    cancel:          ()                                   => void
    onChunk:         (callback: (chunk: string) => void)  => void
    onDone:          (callback: () => void)               => void
    removeListeners: ()                                   => void
  }
}

declare global {
  interface Window {
    debussy: DebussyAPI
  }
}

export {}
