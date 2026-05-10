import { contextBridge } from 'electron'

// Expose a placeholder API surface — populated in future tasks
contextBridge.exposeInMainWorld('electronAPI', {})
