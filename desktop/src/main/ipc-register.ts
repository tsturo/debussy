import { ipcMain, app, BrowserWindow, dialog, shell } from 'electron'
import { join, basename } from 'path'
import { randomUUID } from 'crypto'
import * as fs from 'fs'
import { spawn } from 'child_process'
import { IPC } from '../shared/ipc-channels'
import type { DebussyConfig, WatcherState } from '../shared/types'
import * as dbReader from './db-reader'
import { LogStreamer } from './log-streamer'
import { ConductorBridge } from './conductor-bridge'
import * as workspaceStore from './workspace-store'
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
  auto_start_watcher:   false,
}

// ── Module state ──────────────────────────────────────────────────────────────

let db: Database.Database | null = null
const logStreamer = new LogStreamer()
const conductorBridge = new ConductorBridge()

/** Active project path — set on startup from workspace store and on project switch. */
let activeProjectPath: string = process.cwd()

function getProjectPath(): string {
  return activeProjectPath
}

/** Close current DB and re-open from the given project path. */
function switchProject(projectPath: string): void {
  dbReader.closeDatabase(db)
  db = null
  activeProjectPath = projectPath
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
  // ── Workspace initialisation ───────────────────────────────────────────────
  // Load persisted workspace on startup; validate the path before using it.
  // If the persisted project path no longer exists (e.g. a deleted worktree),
  // fall back to process.cwd() so the app loads the correct database.
  {
    const data = workspaceStore.loadWorkspaces()
    const persistedPath = data.activeProjectPath
    if (persistedPath && fs.existsSync(join(persistedPath, '.takt'))) {
      activeProjectPath = persistedPath
    }
    // If the persisted path has no .takt directory, keep activeProjectPath = process.cwd()
  }


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

  ipcMain.handle(IPC.TASK_ADVANCE, async (_event, id: string, toStage?: string) => {
    const args = ['advance', id]
    if (toStage) args.push('--to', toStage)
    return execTakt(args, getProjectPath())
  })

  ipcMain.handle(IPC.TASK_RELEASE, (_event, id: string) =>
    execTakt(['release', id], getProjectPath())
  )

  ipcMain.handle(IPC.TASK_ADVANCE_TO, (_event, id: string, toStage: string) =>
    execTakt(['advance', id, '--to', toStage], getProjectPath())
  )

  ipcMain.handle(IPC.TASK_BLOCK, (_event, id: string) =>
    execTakt(['block', id], getProjectPath())
  )

  ipcMain.handle(IPC.TASK_COMMENT, (_event, id: string, msg: string) =>
    execTakt(['comment', id, msg], getProjectPath())
  )

  ipcMain.handle(IPC.TASK_CREATE, async (_event, title: string, desc: string) => {
    const result = await execTakt(['create', title, '-d', desc], getProjectPath())
    if (!result.success) return result
    const id = result.stdout.trim() || undefined
    return { ...result, id }
  })

  ipcMain.handle(IPC.TASK_UPDATE, (_event, id: string, fields: { description?: string }) => {
    const args = ['update', id]
    if (fields.description !== undefined) args.push('-d', fields.description)
    return execTakt(args, getProjectPath())
  })

  // ── Conductor IPC ──────────────────────────────────────────────────────────

  ipcMain.handle(IPC.CONDUCTOR_SEND, (_event, text: string, images?: string[], tempPaths?: string[]) => {
    conductorBridge.sendMessage({ text, images, tempPaths }, getProjectPath())
    return { success: true }
  })

  /**
   * Save an image buffer (from clipboard or drag-and-drop) to a temp file.
   * Returns the absolute path of the saved file so the renderer can pass it
   * to the next sendMessage call.  The caller is responsible for passing the
   * path back as a tempPath so it gets deleted after Claude exits.
   */
  ipcMain.handle(IPC.CONDUCTOR_UPLOAD_IMAGE, (_event, data: Uint8Array, mimeType: string) => {
    const extMap: Record<string, string> = {
      'image/png': '.png',
      'image/jpeg': '.jpg',
      'image/jpg': '.jpg',
      'image/gif': '.gif',
      'image/webp': '.webp',
    }
    const ext = extMap[mimeType] ?? '.png'
    const tmpDir = app.getPath('temp')
    const filename = `debussy-img-${randomUUID()}${ext}`
    const filePath = join(tmpDir, filename)
    fs.writeFileSync(filePath, Buffer.from(data))
    return filePath
  })

  /** Open a native file picker restricted to images; returns selected paths. */
  ipcMain.handle(IPC.CONDUCTOR_OPEN_FILE_DIALOG, async (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) ?? BrowserWindow.getFocusedWindow()
    if (!win) return []
    const result = await dialog.showOpenDialog(win, {
      title: 'Attach Images',
      properties: ['openFile', 'multiSelections'],
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp'] }],
    })
    if (result.canceled) return []
    return result.filePaths
  })

  ipcMain.on(IPC.CONDUCTOR_CANCEL, () => {
    conductorBridge.cancelCurrent()
  })

  ipcMain.handle(IPC.CONDUCTOR_CLEAR_CONTEXT, () => {
    const sessionId = conductorBridge.clearWithContext(getProjectPath())
    return { success: true, sessionId }
  })

  ipcMain.handle(IPC.CONDUCTOR_GET_SESSION_ID, () => {
    const sessionId = conductorBridge.getSessionId(getProjectPath())
    if (!sessionId) return { sessionId: null, contextSummary: null, historySummary: null }
    const { contextSummary, historySummary } = conductorBridge.getResumeContext(getProjectPath())
    return { sessionId, contextSummary, historySummary }
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

  // ── Config write handler ───────────────────────────────────────────────────

  ipcMain.handle(IPC.CONFIG_SET, (_event, key: string, value: unknown): { success: boolean; error?: string } => {
    // Validate known keys and value ranges
    if (key === 'max_total_agents') {
      const n = Number(value)
      if (!Number.isInteger(n) || n < 1 || n > 16) {
        return { success: false, error: 'max_total_agents must be an integer between 1 and 16' }
      }
    } else if (key === 'agent_timeout') {
      const n = Number(value)
      if (!Number.isFinite(n) || n <= 0) {
        return { success: false, error: 'agent_timeout must be a positive number' }
      }
    }

    const configPath = join(getProjectPath(), '.debussy', 'config.json')
    const tmpPath    = configPath + '.tmp'

    // Read existing config (or start from empty object)
    let current: Record<string, unknown> = {}
    try {
      current = JSON.parse(fs.readFileSync(configPath, 'utf-8'))
    } catch {
      // Missing or unreadable — start fresh
    }

    current[key] = value

    try {
      fs.writeFileSync(tmpPath, JSON.stringify(current, null, 2), 'utf-8')
      fs.renameSync(tmpPath, configPath)
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  // ── Workspace handlers ─────────────────────────────────────────────────────

  ipcMain.handle(IPC.WORKSPACE_LIST, () => {
    return workspaceStore.loadWorkspaces()
  })

  ipcMain.handle(IPC.WORKSPACE_ADD_GROUP, (_event, name: string, iconLetter: string) => {
    const data = workspaceStore.loadWorkspaces()
    const group: workspaceStore.WorkspaceGroup = {
      id: randomUUID(),
      name,
      iconLetter: iconLetter ?? name.charAt(0).toUpperCase(),
      projects: [],
    }
    data.groups.push(group)
    workspaceStore.saveWorkspaces(data)
    return { success: true, group }
  })

  ipcMain.handle(IPC.WORKSPACE_ADD_PROJECT, (_event, groupId: string, projectPath: string) => {
    // Validate the path has a .takt/ or .git directory
    const hasTakt = fs.existsSync(join(projectPath, '.takt'))
    const hasGit  = fs.existsSync(join(projectPath, '.git'))
    if (!hasTakt && !hasGit) {
      return { success: false, error: 'Path must contain .takt/ or .git directory' }
    }

    const data = workspaceStore.loadWorkspaces()
    const group = data.groups.find((g) => g.id === groupId)
    if (!group) return { success: false, error: `Group not found: ${groupId}` }

    const alreadyAdded = group.projects.some((p) => p.path === projectPath)
    if (alreadyAdded) return { success: false, error: 'Project already in group' }

    group.projects.push({ path: projectPath, name: basename(projectPath) })
    workspaceStore.saveWorkspaces(data)
    return { success: true }
  })

  ipcMain.handle(IPC.WORKSPACE_REMOVE_PROJECT, (_event, groupId: string, projectPath: string) => {
    const data = workspaceStore.loadWorkspaces()
    const wasActive = data.activeProjectPath === projectPath
    const error = workspaceStore.removeProject(data, groupId, projectPath)
    if (error) return { success: false, error }

    workspaceStore.saveWorkspaces(data)

    // Sync in-memory state if the removed project was the active one
    if (wasActive) {
      const newPath = data.activeProjectPath
      if (newPath) {
        switchProject(newPath)
      } else {
        dbReader.closeDatabase(db)
        db = null
        activeProjectPath = process.cwd()
      }
    }

    return { success: true }
  })

  ipcMain.handle(IPC.WORKSPACE_REMOVE_GROUP, (_event, groupId: string) => {
    const data = workspaceStore.loadWorkspaces()
    const wasActiveGroup = data.activeGroupId === groupId
    const error = workspaceStore.removeGroup(data, groupId)
    if (error) return { success: false, error }

    workspaceStore.saveWorkspaces(data)

    if (wasActiveGroup) {
      const newPath = data.activeProjectPath
      if (newPath) {
        switchProject(newPath)
      } else {
        dbReader.closeDatabase(db)
        db = null
        activeProjectPath = process.cwd()
      }
    }

    return { success: true }
  })

  ipcMain.handle(IPC.WORKSPACE_RENAME_GROUP, (_event, groupId: string, newName: string) => {
    const data = workspaceStore.loadWorkspaces()
    const error = workspaceStore.renameGroup(data, groupId, newName)
    if (error) return { success: false, error }
    workspaceStore.saveWorkspaces(data)
    return { success: true }
  })

  ipcMain.handle(IPC.WORKSPACE_SET_ACTIVE, (_event, groupId: string, projectPath: string) => {
    const data = workspaceStore.loadWorkspaces()
    const group = data.groups.find((g) => g.id === groupId)
    if (!group) return { success: false, error: `Group not found: ${groupId}` }

    const project = group.projects.find((p) => p.path === projectPath)
    if (!project) return { success: false, error: 'Project not found in group' }

    data.activeGroupId    = groupId
    data.activeProjectPath = projectPath
    workspaceStore.saveWorkspaces(data)

    // Re-open SQLite for the new project path
    switchProject(projectPath)

    return { success: true }
  })

  // ── App info handler ──────────────────────────────────────────────────────

  ipcMain.handle(IPC.APP_INFO, () => ({
    appVersion:      app.getVersion(),
    electronVersion: process.versions.electron,
    nodeVersion:     process.versions.node,
    chromeVersion:   process.versions.chrome,
  }))

  // ── Shell open external ────────────────────────────────────────────────────

  ipcMain.handle(IPC.SHELL_OPEN_EXTERNAL, (_event, url: string) => {
    // Only allow http/https URLs
    if (!url.startsWith('https://') && !url.startsWith('http://')) {
      return { success: false, error: 'Only http/https URLs are allowed' }
    }
    shell.openExternal(url)
    return { success: true }
  })

  // ── Dialog handlers ───────────────────────────────────────────────────────

  ipcMain.handle(IPC.DIALOG_OPEN_DIRECTORY, async (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) ?? BrowserWindow.getFocusedWindow()
    if (!win) return null
    const result = await dialog.showOpenDialog(win, {
      title: 'Select Project Folder',
      properties: ['openDirectory'],
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

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
 * Uses async spawn (no shell) to avoid blocking the Electron main process.
 */
function execTakt(
  args: string[],
  cwd: string,
): Promise<{ success: boolean; stdout: string; error?: string }> {
  return new Promise((resolve) => {
    const child = spawn('takt', args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (d) => { stdout += d })
    child.stderr.on('data', (d) => { stderr += d })
    child.on('close', (code) => {
      resolve({ success: code === 0, stdout: stdout.trim(), error: stderr.trim() || undefined })
    })
    child.on('error', (err) => {
      resolve({ success: false, stdout: '', error: err.message })
    })
  })
}
