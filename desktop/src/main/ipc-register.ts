import { ipcMain } from 'electron'
import { IPC } from '../shared/ipc-channels'
import type { DebussyConfig, WatcherState } from '../shared/types'

const DEFAULT_CONFIG: DebussyConfig = {
  max_total_agents:  8,
  use_tmux_windows:  false,
  base_branch:       null,
  paused:            false,
  agent_timeout:     3600,
  agent_provider:    'claude',
  role_models:       {},
  docs_path:         null,
  notify_conductor:  false,
  max_role_agents:   {},
  monitor_interval:  240,
  project_type:      null,
  conductor_session_id: null,
  test_command:      null,
}

export function registerIPC(): void {
  // ── Read-only stubs ──────────────────────────────────────────────────────
  ipcMain.handle(IPC.TASKS_LIST,     () => [])
  ipcMain.handle(IPC.TASK_GET,       () => null)
  ipcMain.handle(IPC.AGENTS_LIST,    (): WatcherState => ({}))
  ipcMain.handle(IPC.AGENT_LOG,      () => '')
  ipcMain.handle(IPC.CONFIG_GET,     () => DEFAULT_CONFIG)
  ipcMain.handle(IPC.WATCHER_STATUS, () => ({ running: false }))

  // ── Write-action stubs ───────────────────────────────────────────────────
  ipcMain.handle(IPC.TASK_ADVANCE,  () => ({ success: true }))
  ipcMain.handle(IPC.TASK_BLOCK,    () => ({ success: true }))
  ipcMain.handle(IPC.TASK_COMMENT,  () => ({ success: true }))
  ipcMain.handle(IPC.TASK_CREATE,   () => ({ success: true }))
  ipcMain.handle(IPC.CONFIG_SET,    () => ({ success: true }))
  ipcMain.handle(IPC.WATCHER_START, () => ({ success: true }))
  ipcMain.handle(IPC.WATCHER_STOP,  () => ({ success: true }))
  ipcMain.handle(IPC.CONDUCTOR_SEND,   () => ({ success: true }))
  ipcMain.handle(IPC.CONDUCTOR_STREAM, () => ({ success: true }))
}
