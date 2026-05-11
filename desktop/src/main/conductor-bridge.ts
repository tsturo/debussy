import { spawn, ChildProcess } from 'child_process'
import { readFileSync, writeFileSync, renameSync, unlinkSync, existsSync } from 'fs'
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
   * Generate a fresh session ID and send the project context files
   * (.debussy/conductor-context.md + .debussy/conductor-history.md) as the
   * first message so Claude starts fresh but with full project awareness.
   * If neither file exists the session is still rotated (blank start).
   * Returns the new session ID.
   */
  clearWithContext(cwd: string): string {
    const newId = randomUUID()
    this.sessionId = newId
    this.persistSessionId(cwd, newId)

    const contextPath = join(cwd, '.debussy', 'conductor-context.md')
    const historyPath = join(cwd, '.debussy', 'conductor-history.md')

    let contextContent = ''
    let historyContent = ''
    try { if (existsSync(contextPath)) contextContent = readFileSync(contextPath, 'utf-8') } catch { /* missing — skip */ }
    try { if (existsSync(historyPath)) historyContent = readFileSync(historyPath, 'utf-8') } catch { /* missing — skip */ }

    if (contextContent || historyContent) {
      const parts = ['Here is the project context:']
      if (contextContent) parts.push(contextContent)
      if (historyContent) parts.push(historyContent)
      this.sendMessage({ text: parts.join('\n\n') }, cwd)
    }

    return newId
  }

  /**
   * Read .debussy/conductor-context.md and .debussy/conductor-history.md and
   * extract one-line summaries from each.  Returns nulls for files that are
   * missing, unreadable, or contain no parseable content.
   */
  getResumeContext(cwd: string): { contextSummary: string | null; historySummary: string | null } {
    const contextPath = join(cwd, '.debussy', 'conductor-context.md')
    const historyPath = join(cwd, '.debussy', 'conductor-history.md')

    let contextSummary: string | null = null
    let historySummary: string | null = null

    try {
      if (existsSync(contextPath)) {
        contextSummary = this.extractContextSummary(readFileSync(contextPath, 'utf-8'))
      }
    } catch { /* unreadable — skip */ }

    try {
      if (existsSync(historyPath)) {
        historySummary = this.extractHistorySummary(readFileSync(historyPath, 'utf-8'))
      }
    } catch { /* unreadable — skip */ }

    return { contextSummary, historySummary }
  }

  /**
   * Return the persisted session ID, or null if none has been created yet.
   * Does NOT generate a new UUID as a side effect (unlike getOrCreateSessionId).
   */
  getSessionId(cwd: string): string | null {
    if (this.sessionId) return this.sessionId
    try {
      const config = JSON.parse(readFileSync(join(cwd, '.debussy', 'config.json'), 'utf-8'))
      if (typeof config?.conductor_session_id === 'string' && config.conductor_session_id) {
        this.sessionId = config.conductor_session_id
        return this.sessionId
      }
    } catch {
      // Config missing or unreadable
    }
    return null
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
    const tmpPath = configPath + '.tmp'
    writeFileSync(tmpPath, JSON.stringify(config, null, 2) + '\n', 'utf-8')
    renameSync(tmpPath, configPath)
  }

  /**
   * Extract a short summary from conductor-context.md.
   * Prefers the first content line under "## Status"; falls back to the first
   * two non-heading content lines joined with " · ".
   */
  private extractContextSummary(content: string): string | null {
    const lines = content.split('\n')

    // Look for ## Status section and take first content line
    let inStatus = false
    for (const line of lines) {
      if (/^##\s+Status\b/i.test(line)) { inStatus = true; continue }
      if (inStatus) {
        if (line.startsWith('#')) break
        const trimmed = line.trim().replace(/\*\*/g, '')
        if (trimmed) return trimmed.length > 70 ? trimmed.slice(0, 70) + '…' : trimmed
      }
    }

    // Fallback: first 2 non-empty, non-heading lines
    const contentLines = lines
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#') && l !== '---')
      .slice(0, 2)

    if (contentLines.length === 0) return null
    const joined = contentLines.join(' · ')
    return joined.length > 70 ? joined.slice(0, 70) + '…' : joined
  }

  /**
   * Extract a short summary from conductor-history.md.
   * Returns the last ## heading that isn't "Cumulative"; falls back to the
   * last non-empty, non-heading content line.
   */
  private extractHistorySummary(content: string): string | null {
    const lines = content.split('\n')
    let lastPhaseHeading: string | null = null

    for (const line of lines) {
      const m = line.match(/^##\s+(.+)/)
      if (m) {
        const title = m[1].trim()
        if (!/^cumulative/i.test(title)) lastPhaseHeading = title
      }
    }

    if (lastPhaseHeading) {
      // Strip date prefix like "[2026-05-10] "
      const cleaned = lastPhaseHeading.replace(/^\[\d{4}-\d{2}-\d{2}\]\s+/, '')
      return cleaned.length > 70 ? cleaned.slice(0, 70) + '…' : cleaned
    }

    // Fallback: last non-empty, non-heading line
    const contentLines = lines.map((l) => l.trim()).filter((l) => l && !l.startsWith('#'))
    if (contentLines.length === 0) return null
    const last = contentLines[contentLines.length - 1]
    return last.length > 70 ? last.slice(0, 70) + '…' : last
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
