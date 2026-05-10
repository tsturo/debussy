import type { Task, WatcherState, DebussyConfig } from '../../shared/types'

interface DebussyAPI {
  tasks: {
    list:    ()                            => Promise<Task[]>
    get:     (id: string)                  => Promise<Task | null>
    advance: (id: string)                  => Promise<{ success: boolean }>
    block:   (id: string)                  => Promise<{ success: boolean }>
    comment: (id: string, msg: string)     => Promise<{ success: boolean }>
    create:  (title: string, desc: string) => Promise<{ success: boolean }>
  }
  agents: {
    list: ()              => Promise<WatcherState>
    log:  (name: string)  => Promise<string>
  }
  config: {
    get: () => Promise<DebussyConfig>
  }
  watcher: {
    status: () => Promise<{ running: boolean }>
  }
}

declare global {
  interface Window {
    debussy: DebussyAPI
  }
}

export {}
