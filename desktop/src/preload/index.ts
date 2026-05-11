import { contextBridge, ipcRenderer } from 'electron'
import { IPC } from '../shared/ipc-channels'

contextBridge.exposeInMainWorld('debussy', {
  tasks: {
    list:    ()                        => ipcRenderer.invoke(IPC.TASKS_LIST),
    get:     (id: string)              => ipcRenderer.invoke(IPC.TASK_GET, id),
    advance:   (id: string)                      => ipcRenderer.invoke(IPC.TASK_ADVANCE, id),
    advanceTo: (id: string, toStage: string)     => ipcRenderer.invoke(IPC.TASK_ADVANCE_TO, id, toStage),
    release:   (id: string)                      => ipcRenderer.invoke(IPC.TASK_RELEASE, id),
    block:     (id: string)                      => ipcRenderer.invoke(IPC.TASK_BLOCK, id),
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
    get: ()                            => ipcRenderer.invoke(IPC.CONFIG_GET),
    set: (key: string, value: unknown) => ipcRenderer.invoke(IPC.CONFIG_SET, key, value),
  },
  watcher: {
    status: () => ipcRenderer.invoke(IPC.WATCHER_STATUS),
    start:  () => ipcRenderer.invoke(IPC.WATCHER_START),
    stop:   () => ipcRenderer.invoke(IPC.WATCHER_STOP),
  },
  conductor: {
    send:            (text: string, images?: string[], tempPaths?: string[]) =>
                       ipcRenderer.invoke(IPC.CONDUCTOR_SEND, text, images, tempPaths),
    cancel:          ()                                         => ipcRenderer.send(IPC.CONDUCTOR_CANCEL),
    newSession:      ()                                         => ipcRenderer.invoke(IPC.CONDUCTOR_NEW_SESSION),
    clearContext:    ()                                         => ipcRenderer.invoke(IPC.CONDUCTOR_CLEAR_CONTEXT),
    getSessionId:    ()                                         => ipcRenderer.invoke(IPC.CONDUCTOR_GET_SESSION_ID),
    onChunk:         (callback: (chunk: string) => void)        => ipcRenderer.on(IPC.CONDUCTOR_RESPONSE_CHUNK, (_event, chunk) => callback(chunk)),
    onDone:          (callback: () => void)                     => ipcRenderer.on(IPC.CONDUCTOR_RESPONSE_DONE, () => callback()),
    removeListeners: ()                                         => {
      ipcRenderer.removeAllListeners(IPC.CONDUCTOR_RESPONSE_CHUNK)
      ipcRenderer.removeAllListeners(IPC.CONDUCTOR_RESPONSE_DONE)
    },
    uploadImage:     (buffer: ArrayBuffer, mimeType: string)   =>
                       ipcRenderer.invoke(IPC.CONDUCTOR_UPLOAD_IMAGE, new Uint8Array(buffer), mimeType),
    openFileDialog:  ()                                        =>
                       ipcRenderer.invoke(IPC.CONDUCTOR_OPEN_FILE_DIALOG) as Promise<string[]>,
  },
  workspace: {
    list:          ()                                                         => ipcRenderer.invoke(IPC.WORKSPACE_LIST),
    addGroup:      (name: string, iconLetter: string)                         => ipcRenderer.invoke(IPC.WORKSPACE_ADD_GROUP, name, iconLetter),
    addProject:    (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_ADD_PROJECT, groupId, projectPath),
    removeProject: (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_REMOVE_PROJECT, groupId, projectPath),
    removeGroup:   (groupId: string)                                          => ipcRenderer.invoke(IPC.WORKSPACE_REMOVE_GROUP, groupId),
    renameGroup:   (groupId: string, newName: string)                         => ipcRenderer.invoke(IPC.WORKSPACE_RENAME_GROUP, groupId, newName),
    setActive:     (groupId: string, projectPath: string)                     => ipcRenderer.invoke(IPC.WORKSPACE_SET_ACTIVE, groupId, projectPath),
  },
  dialog: {
    openDirectory: () => ipcRenderer.invoke(IPC.DIALOG_OPEN_DIRECTORY),
  },
  app: {
    info: () => ipcRenderer.invoke(IPC.APP_INFO),
  },
  shell: {
    openExternal: (url: string) => ipcRenderer.invoke(IPC.SHELL_OPEN_EXTERNAL, url),
  },
})
