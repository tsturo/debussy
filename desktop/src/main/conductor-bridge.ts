import { spawn, ChildProcess } from 'child_process'
import { readFileSync } from 'fs'
import { join } from 'path'
import { BrowserWindow } from 'electron'
import { IPC } from '../shared/ipc-channels'

const DEFAULT_MODEL = 'claude-sonnet-4-6'

export class ConductorBridge {
  private currentProcess: ChildProcess | null = null

  /**
   * Spawn a claude CLI process with the conductor system prompt and stream
   * its output to the renderer via IPC events.
   */
  sendMessage(message: string, cwd: string): void {
    this.cancelCurrent()

    const systemPrompt = this.readSystemPrompt(cwd)
    if (systemPrompt === null) {
      const promptPath = join(cwd, 'src', 'debussy', 'prompts', 'conductor.md')
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, `Error: conductor prompt not found at ${promptPath}`)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      return
    }

    const model = this.readModel(cwd)
    const args = ['--print', '--system-prompt', systemPrompt, '--model', model, message]

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

    child.stdout?.on('data', (chunk: Buffer) => {
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, chunk.toString())
    })

    child.on('error', (err: NodeJS.ErrnoException) => {
      const msg = err.code === 'ENOENT'
        ? 'Error: claude CLI not found. Please install the Claude CLI and ensure it is on your PATH.'
        : `Error: ${err.message}`
      this.broadcast(IPC.CONDUCTOR_RESPONSE_CHUNK, msg)
      this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      if (this.currentProcess === child) {
        this.currentProcess = null
      }
    })

    child.on('close', (_code: number | null, signal: string | null) => {
      if (signal !== 'SIGTERM' && signal !== 'SIGKILL') {
        // Normal exit — signal done
        this.broadcast(IPC.CONDUCTOR_RESPONSE_DONE, null)
      }
      if (this.currentProcess === child) {
        this.currentProcess = null
      }
    })
  }

  /** Kill the running process, if any. */
  cancelCurrent(): void {
    if (this.currentProcess) {
      this.currentProcess.kill()
      this.currentProcess = null
    }
  }

  // ── Private helpers ──────────────────────────────────────────────────────────

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

  private broadcast(channel: string, data: unknown): void {
    for (const win of BrowserWindow.getAllWindows()) {
      win.webContents.send(channel, data)
    }
  }
}
