import { spawn, ChildProcess } from 'child_process'
import { readFileSync, writeFileSync, unlinkSync } from 'fs'
import { join } from 'path'
import { randomUUID } from 'crypto'
import { BrowserWindow } from 'electron'
import { IPC } from '../shared/ipc-channels'

const DEFAULT_MODEL = 'claude-sonnet-4-6'

export class ConductorBridge {
  private currentProcess: ChildProcess | null = null
  private sessionId: string | null = null

  /**
   * Spawn a claude CLI process with the conductor system prompt and stream
   * its output to the renderer via IPC events.
   *
   * @param payload.text    The user's text message.
   * @param payload.images  Optional array of absolute image file paths; each
   *                        is forwarded to Claude via --image flags.
   * @param payload.tempPaths  Paths of temp files to delete after the process
   *                           exits (i.e. images uploaded from the clipboard).
   */
  sendMessage(
    payload: { text: string; images?: string[]; tempPaths?: string[] },
    cwd: string,
  ): void {
    this.cancelCurrent()

    const systemPrompt = this.readSystemPrompt(cwd)
    if (systemPrompt === null) {
      const promptPath = join(cwd, 'src', 'debussy', 'prompts', 'conductor.md')
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, `Error: conductor prompt not found at ${promptPath}`)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      return
    }

    const sessionId = this.getOrCreateSessionId(cwd)
    const model = this.readModel(cwd)

    const imageFlags = (payload.images ?? []).flatMap((p) => ['--image', p])
    const args = [
      '--print',
      '--session-id', sessionId,
      '--system-prompt', systemPrompt,
      '--model', model,
      ...imageFlags,
      payload.text,
    ]

    let child: ChildProcess
    try {
      child = spawn('claude', args, { cwd })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, `Error: ${msg}`)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      return
    }

    this.currentProcess = child
    const tempPaths = payload.tempPaths ?? []

    child.stdout?.on('data', (chunk: Buffer) => {
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, chunk.toString())
    })

    child.on('error', (err: NodeJS.ErrnoException) => {
      const msg = err.code === 'ENOENT'
        ? 'Error: claude CLI not found. Please install the Claude CLI and ensure it is on your PATH.'
        : `Error: ${err.message}`
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, msg)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      this.cleanupTempFiles(tempPaths)
      if (this.currentProcess === child) {
        this.currentProcess = null
      }
    })

    child.on('close', (_code: number | null, signal: string | null) => {
      if (signal !== 'SIGTERM' && signal !== 'SIGKILL') {
        // Normal exit — signal done
        this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      }
      this.cleanupTempFiles(tempPaths)
      if (this.currentProcess === child) {
        this.currentProcess = null
      }
    })
  }

  /**
   * Generate a fresh session ID, persist it to config, and clear the
   * in-memory cache so the next sendMessage call picks it up.
   */
  newSession(cwd: string): void {
    const newId = randomUUID()
    this.sessionId = newId
    this.persistSessionId(cwd, newId)
  }

  /** Kill the running process, if any. */
  cancelCurrent(): void {
    if (this.currentProcess) {
      this.currentProcess.kill()
      this.currentProcess = null
    }
  }

  // ── Private helpers ──────────────────────────────────────────────────────────

  /**
   * Return the in-memory session ID, loading from config on first call.
   * If no ID exists in config, a new UUID is generated and saved.
   */
  private getOrCreateSessionId(cwd: string): string {
    if (this.sessionId) return this.sessionId

    // Try to read from persisted config
    try {
      const config = JSON.parse(readFileSync(join(cwd, '.debussy', 'config.json'), 'utf-8'))
      if (typeof config?.conductor_session_id === 'string' && config.conductor_session_id) {
        this.sessionId = config.conductor_session_id
        return this.sessionId
      }
    } catch {
      // Config missing or unreadable — fall through to generate
    }

    // First launch: generate, persist, and cache
    const id = randomUUID()
    this.persistSessionId(cwd, id)
    this.sessionId = id
    return id
  }

  /** Write conductor_session_id into .debussy/config.json. */
  private persistSessionId(cwd: string, id: string): void {
    const configPath = join(cwd, '.debussy', 'config.json')
    let config: Record<string, unknown> = {}
    try {
      config = JSON.parse(readFileSync(configPath, 'utf-8'))
    } catch {
      // File missing or malformed — start from empty object
    }
    config['conductor_session_id'] = id
    writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n', 'utf-8')
  }

  private readSystemPrompt(cwd: string): string | null {
    try {
      return readFileSync(join(cwd, 'src', 'debussy', 'prompts', 'conductor.md'), 'utf-8')
    } catch {
      return null
    }
  }

  private readModel(cwd: string): string {
    try {
      const config = JSON.parse(readFileSync(join(cwd, '.debussy', 'config.json'), 'utf-8'))
      return config?.role_models?.conductor ?? DEFAULT_MODEL
    } catch {
      return DEFAULT_MODEL
    }
  }

  private cleanupTempFiles(paths: string[]): void {
    for (const p of paths) {
      try { unlinkSync(p) } catch { /* ignore — file may already be gone */ }
    }
  }

  private broadcast(channel: string, data: unknown): void {
    for (const win of BrowserWindow.getAllWindows()) {
      win.webContents.send(channel, data)
    }
  }
}
