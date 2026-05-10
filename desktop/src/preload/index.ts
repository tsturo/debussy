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
    list:              ()                                                    => ipcRenderer.invoke(IPC.AGENTS_LIST),
    startLog:          (agentName: string)                                   => ipcRenderer.send(IPC.AGENT_LOG, agentName),
    stopLog:           (agentName: string)                                   => ipcRenderer.send(IPC.AGENT_LOG_STOP, agentName),
    onLogLine:         (callback: (data: { agent: string; line: string }) => void) =>
                         ipcRenderer.on('agent-log:line', (_event, data) => callback(data)),
    removeLogListener: ()                                                    => ipcRenderer.removeAllListeners('agent-log:line'),
  },
  config: {
    get: () => ipcRenderer.invoke(IPC.CONFIG_GET),
  },
  watcher: {
    status: () => ipcRenderer.invoke(IPC.WATCHER_STATUS),
  },
})
