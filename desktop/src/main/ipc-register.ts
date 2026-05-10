import { ipcMain, app, BrowserWindow } from 'electron'
import { join } from 'path'
import * as fs from 'fs'
import { spawn, spawnSync } from 'child_process'
import { IPC } from '../shared/ipc-channels'
import type { DebussyConfig, WatcherState } from '../shared/types'
import * as dbReader from './db-reader'
import { LogStreamer } from './log-streamer'
import { ConductorBridge } from './conductor-bridge'
import type Database from 'better-sqlite3'

const DEFAULT_CONFIG: DebussyConfig = {
  max_total_agents:     8,
  use_tmux_windows:     false,
  base_branch:          null,
  paused:               false,
  agent_timeout:        3600,
  agent_provider:       'claude',
  role_models:          {},
  docs_path:            null,
  notify_conductor:     false,
  max_role_agents:      {},
  monitor_interval:     240,
  project_type:         null,
  conductor_session_id: null,
  test_command:         null,
}

// ── Module state ──────────────────────────────────────────────────────────────

let db: Database.Database | null = null
const logStreamer = new LogStreamer()
const conductorBridge = new ConductorBridge()

function getProjectPath(): string {
  return process.cwd()
}

/**
 * Return the open DB handle, opening it lazily on first call.
 * Returns null when .takt/takt.db does not exist yet (valid for new projects).
 * Re-tries on every call while db is null so a newly-initialised project is
 * picked up automatically.
 */
function getDb(): Database.Database | null {
  if (!db) {
    const dbPath = join(getProjectPath(), '.takt', 'takt.db')
    db = dbReader.openDatabase(dbPath)
  }
  return db
}

// ── IPC registration ──────────────────────────────────────────────────────────

export function registerIPC(): void {
  // ── Read-only handlers ─────────────────────────────────────────────────────

  ipcMain.handle(IPC.TASKS_LIST, () => {
    return dbReader.listTasks(getDb())
  })

  ipcMain.handle(IPC.TASK_GET, (_event, id: string) => {
    const handle = getDb()
    if (!handle) return null
    const task = dbReader.getTask(handle, id)
    if (!task) return null
    const deps = dbReader.getTaskDeps(handle, id)
    const log  = dbReader.getTaskLog(handle, id)
    return { ...task, deps, log }
  })

  ipcMain.handle(IPC.AGENTS_LIST, (): WatcherState => {
    const statePath = join(getProjectPath(), '.debussy', 'watcher_state.json')
    try {
      const parsed = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
      return typeof parsed === 'object' && parsed !== null ? parsed : {}
    } catch {
      return {}
    }
  })

  ipcMain.on(IPC.AGENT_LOG, (event, name: string) => {
    const statePath = join(getProjectPath(), '.debussy', 'watcher_state.json')
    try {
      const state: WatcherState = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
      const entry = Object.values(state).find((a) => a.agent === name)
      if (!entry) return

      const logPath = join(getProjectPath(), entry.log)
      const webContentsId = event.sender.id
      logStreamer.startTailing(logPath, (line) => {
        const win = BrowserWindow.getAllWindows().find(
          (w) => w.webContents.id === webContentsId,
        )
        win?.webContents.send(IPC.AGENT_LOG_LINE, { agent: name, line })
      })
    } catch {
      // state file missing or malformed — no-op
    }
  })

  ipcMain.on(IPC.AGENT_LOG_STOP, (_event, name: string) => {
    const statePath = join(getProjectPath(), '.debussy', 'watcher_state.json')
    try {
      const state: WatcherState = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
      const entry = Object.values(state).find((a) => a.agent === name)
      if (!entry) return
      logStreamer.stopTailing(join(getProjectPath(), entry.log))
    } catch {
      // nothing to stop
    }
  })

  ipcMain.handle(IPC.CONFIG_GET, (): DebussyConfig => {
    const configPath = join(getProjectPath(), '.debussy', 'config.json')
    try {
      const parsed = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
      return { ...DEFAULT_CONFIG, ...parsed }
    } catch {
      return { ...DEFAULT_CONFIG }
    }
  })

  ipcMain.handle(IPC.WATCHER_STATUS, () => {
    const lockPath = join(getProjectPath(), '.debussy', 'watcher.lock')
    if (!fs.existsSync(lockPath)) return { running: false }
    try {
      const pid = parseInt(fs.readFileSync(lockPath, 'utf-8').trim(), 10)
      if (isNaN(pid)) return { running: false }
      try {
        process.kill(pid, 0) // signal 0: existence check only, no signal sent
        return { running: true, pid }
      } catch {
        return { running: false }
      }
    } catch {
      return { running: false }
    }
  })

  // ── Write-action handlers ──────────────────────────────────────────────────

  ipcMain.handle(IPC.TASK_ADVANCE, (_event, id: string) =>
    runTakt(['advance', id])
  )

  ipcMain.handle(IPC.TASK_BLOCK, (_event, id: string) =>
    runTakt(['block', id])
  )

  ipcMain.handle(IPC.TASK_COMMENT, (_event, id: string, msg: string) =>
    runTakt(['comment', id, msg])
  )

  ipcMain.handle(IPC.TASK_CREATE, (_event, title: string, desc: string) => {
    const result = runTakt(['create', title, '-d', desc])
    if (!result.success) return result
    const id = result.output?.trim() || undefined
    return { ...result, id }
  })

  // ── Conductor IPC ──────────────────────────────────────────────────────────

  ipcMain.handle(IPC.CONDUCTOR_SEND, (_event, message: string) => {
    conductorBridge.sendMessage(message, getProjectPath())
    return { success: true }
  })

  ipcMain.on(IPC.CONDUCTOR_CANCEL, () => {
    conductorBridge.cancelCurrent()
  })

  // ── Watcher control handlers ───────────────────────────────────────────────

  ipcMain.handle(IPC.WATCHER_START, () => {
    const lockPath = join(getProjectPath(), '.debussy', 'watcher.lock')
    // Check if already running
    if (fs.existsSync(lockPath)) {
      try {
        const pid = parseInt(fs.readFileSync(lockPath, 'utf-8').trim(), 10)
        if (!isNaN(pid)) {
          try {
            process.kill(pid, 0) // existence check only
            return { success: true, alreadyRunning: true }
          } catch {
            // PID in lock file is stale — fall through to start
          }
        }
      } catch {
        // Lock file unreadable — fall through to start
      }
    }
    try {
      const child = spawn('debussy', ['watch'], {
        cwd:      getProjectPath(),
        detached: true,
        stdio:    'ignore',
      })
      child.unref()
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle(IPC.WATCHER_STOP, () => {
    const lockPath = join(getProjectPath(), '.debussy', 'watcher.lock')
    if (!fs.existsSync(lockPath)) {
      return { success: false, error: 'Watcher is not running' }
    }
    try {
      const pid = parseInt(fs.readFileSync(lockPath, 'utf-8').trim(), 10)
      if (isNaN(pid)) return { success: false, error: 'Invalid PID in lock file' }
      process.kill(pid, 'SIGTERM')
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  // ── Stubbed handlers (future tasks) ───────────────────────────────────────

  ipcMain.handle(IPC.CONFIG_SET, () => ({ success: true }))

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  app.on('will-quit', () => {
    conductorBridge.cancelCurrent()
    logStreamer.stopAll()
    dbReader.closeDatabase(db)
    db = null
  })
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Run a takt sub-command with the given positional arguments.
 * Uses spawnSync (no shell) to avoid any command-injection risk.
 */
function runTakt(
  args: string[]
): { success: boolean; output?: string; error?: string } {
  const result = spawnSync('takt', args, {
    cwd:      getProjectPath(),
    encoding: 'utf-8',
  })
  if (result.status === 0) {
    return { success: true, output: result.stdout }
  }
  const error =
    result.stderr?.trim() ||
    result.error?.message ||
    `takt exited with code ${result.status}`
  return { success: false, error }
}
