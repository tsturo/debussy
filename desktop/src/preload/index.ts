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
    start:  () => ipcRenderer.invoke(IPC.WATCHER_START),
    stop:   () => ipcRenderer.invoke(IPC.WATCHER_STOP),
  },
  conductor: {
    send:            (message: string)                          => ipcRenderer.invoke(IPC.CONDUCTOR_SEND, message),
    cancel:          ()                                         => ipcRenderer.send(IPC.CONDUCTOR_CANCEL),
    onChunk:         (callback: (chunk: string) => void)        => ipcRenderer.on(IPC.CONDUCTOR_RESPONSE_CHUNK, (_event, chunk) => callback(chunk)),
    onDone:          (callback: () => void)                     => ipcRenderer.on(IPC.CONDUCTOR_RESPONSE_DONE, () => callback()),
    removeListeners: ()                                         => {
      ipcRenderer.removeAllListeners(IPC.CONDUCTOR_RESPONSE_CHUNK)
      ipcRenderer.removeAllListeners(IPC.CONDUCTOR_RESPONSE_DONE)
    },
  },
  workspace: {
    list:          ()                                                         => ipcRenderer.invoke(IPC.WORKSPACE_LIST),
    addGroup:      (name: string, iconLetter: string)                         => ipcRenderer.invoke(IPC.WORKSPACE_ADD_GROUP, name, iconLetter),
    addProject:    (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_ADD_PROJECT, groupId, projectPath),
    removeProject: (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_REMOVE_PROJECT, groupId, projectPath),
    setActive:     (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_SET_ACTIVE, groupId, projectPath),
  },
})
