import { ipcMain, app, BrowserWindow } from 'electron'
import { join } from 'path'
import * as fs from 'fs'
import { spawnSync } from 'child_process'
import { IPC } from '../shared/ipc-channels'
import type { DebussyConfig, WatcherState } from '../shared/types'
import * as dbReader from './db-reader'
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

/** Active log watchers keyed by agent name. Value is the cleanup function. */
const logWatchers = new Map<string, () => void>()

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
    stopLogWatcher(name)

    const statePath = join(getProjectPath(), '.debussy', 'watcher_state.json')
    try {
      const state: WatcherState = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
      const entry = Object.values(state).find((a) => a.agent === name)
      if (!entry) return

      const logPath = join(getProjectPath(), entry.log)
      if (!fs.existsSync(logPath)) return

      const webContentsId = event.sender.id
      let position = fs.statSync(logPath).size

      function sendNewLines(): void {
        try {
          const stat = fs.statSync(logPath)
          if (stat.size <= position) return

          const length = stat.size - position
          const buffer = Buffer.alloc(length)
          const fd = fs.openSync(logPath, 'r')
          try {
            fs.readSync(fd, buffer, 0, length, position)
          } finally {
            fs.closeSync(fd)
          }
          position = stat.size

          const sender = BrowserWindow.getAllWindows().find(
            (w) => w.webContents.id === webContentsId,
          )
          if (!sender) return

          const lines = buffer.toString('utf-8').split('\n')
          for (const line of lines) {
            if (line.length > 0) {
              sender.webContents.send('agent-log:line', { agent: name, line })
            }
          }
        } catch {
          // log file may have been rotated or removed — ignore
        }
      }

      const watcher = fs.watch(logPath, sendNewLines)
      logWatchers.set(name, () => watcher.close())
    } catch {
      // state file missing or malformed — no-op
    }
  })

  ipcMain.on(IPC.AGENT_LOG_STOP, (_event, name: string) => {
    stopLogWatcher(name)
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

  // ── Stubbed handlers (future tasks) ───────────────────────────────────────

  ipcMain.handle(IPC.CONFIG_SET,       () => ({ success: true }))
  ipcMain.handle(IPC.WATCHER_START,    () => ({ success: true }))
  ipcMain.handle(IPC.WATCHER_STOP,     () => ({ success: true }))
  ipcMain.handle(IPC.CONDUCTOR_SEND,   () => ({ success: true }))
  ipcMain.handle(IPC.CONDUCTOR_STREAM, () => ({ success: true }))

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  app.on('will-quit', () => {
    dbReader.closeDatabase(db)
    db = null
    for (const cleanup of logWatchers.values()) {
      cleanup()
    }
    logWatchers.clear()
  })
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Stop and remove the active watcher for the given agent name, if any. */
function stopLogWatcher(name: string): void {
  const cleanup = logWatchers.get(name)
  if (cleanup) {
    cleanup()
    logWatchers.delete(name)
  }
}

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
