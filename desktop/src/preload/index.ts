import { contextBridge, ipcRenderer } from 'electron'
import { IPC } from '../shared/ipc-channels'

contextBridge.exposeInMainWorld('debussy', {
  tasks: {
    list:    ()                        => ipcRenderer.invoke(IPC.TASKS_LIST),
    get:     (id: string)              => ipcRenderer.invoke(IPC.TASK_GET, id),
    advance: (id: string)              => ipcRenderer.invoke(IPC.TASK_ADVANCE, id),
    block:   (id: string)              => ipcRenderer.invoke(IPC.TASK_BLOCK, id),
    comment: (id: string, msg: string) => ipcRenderer.invoke(IPC.TASK_COMMENT, id, msg),
    create:  (title: string, desc: string) => ipcRenderer.invoke(IPC.TASK_CREATE, title, desc),
  },
  agents: {
    list: ()              => ipcRenderer.invoke(IPC.AGENTS_LIST),
    log:  (name: string)  => ipcRenderer.invoke(IPC.AGENT_LOG, name),
  },
  config: {
    get: () => ipcRenderer.invoke(IPC.CONFIG_GET),
  },
  watcher: {
    status: () => ipcRenderer.invoke(IPC.WATCHER_STATUS),
  },
})
