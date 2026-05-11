import * as fs from 'fs'
import { dirname } from 'path'

interface TailState {
  watcher:        fs.FSWatcher | null
  creationWatcher: fs.FSWatcher | null
  position:       number
  debounceTimer:  ReturnType<typeof setTimeout> | null
}

export class LogStreamer {
  private tails     = new Map<string, TailState>()
  private callbacks = new Map<string, (line: string) => void>()

  startTailing(logPath: string, callback: (line: string) => void): void {
    this.stopTailing(logPath)
    this.callbacks.set(logPath, callback)

    if (fs.existsSync(logPath)) {
      this._startWatcher(logPath)
    } else {
      this._watchForCreation(logPath)
    }
  }

  stopTailing(logPath: string): void {
    const state = this.tails.get(logPath)
    if (state) {
      if (state.debounceTimer) clearTimeout(state.debounceTimer)
      state.watcher?.close()
      state.creationWatcher?.close()
      this.tails.delete(logPath)
    }
    this.callbacks.delete(logPath)
  }

  stopAll(): void {
    for (const logPath of [...this.tails.keys()]) {
      this.stopTailing(logPath)
    }
  }

  // ── Private helpers ─────────────────────────────────────────────────────────

  /**
   * Start watching an existing file for new content.
   *
   * @param logPath   Absolute path to the file (must exist).
   * @param fromStart When true, start reading from byte 0 instead of the end.
   *                  Use this when the file was just created so that any
   *                  content already written at creation time is not skipped.
   */
  private _startWatcher(logPath: string, fromStart = false): void {
    let endPosition: number
    try {
      endPosition = fs.statSync(logPath).size
    } catch {
      endPosition = 0
    }

    const state: TailState = {
      watcher:        null,
      creationWatcher: null,
      position:       fromStart ? 0 : endPosition,
      debounceTimer:  null,
    }

    try {
      const watcher = fs.watch(logPath, () => {
        if (state.debounceTimer) clearTimeout(state.debounceTimer)
        state.debounceTimer = setTimeout(() => {
          this._readNewContent(logPath, state)
        }, 100)
      })
      watcher.on('error', () => {})
      state.watcher = watcher
    } catch {
      // file may have been removed before we could watch it
    }

    this.tails.set(logPath, state)

    // If starting from the beginning, emit any content already in the file.
    if (fromStart && endPosition > 0) {
      this._readNewContent(logPath, state)
    }
  }

  private _watchForCreation(logPath: string): void {
    const dir = dirname(logPath)
    const state: TailState = {
      watcher:        null,
      creationWatcher: null,
      position:       0,
      debounceTimer:  null,
    }

    try {
      const creationWatcher = fs.watch(dir, (_eventType, filename) => {
        if (filename && logPath.endsWith(filename) && fs.existsSync(logPath)) {
          state.creationWatcher?.close()
          state.creationWatcher = null
          this.tails.delete(logPath)
          // fromStart=true: read everything written at and after creation
          this._startWatcher(logPath, true)
        }
      })
      creationWatcher.on('error', () => {})
      state.creationWatcher = creationWatcher
      this.tails.set(logPath, state)
    } catch {
      // parent directory doesn't exist — nothing to watch
    }
  }

  private _readNewContent(logPath: string, state: TailState): void {
    let size: number
    try {
      size = fs.statSync(logPath).size
    } catch {
      return  // file removed
    }

    // Handle truncation (e.g. log rotation)
    if (size < state.position) {
      state.position = 0
    }

    if (size === state.position) return

    const MAX_READ_SIZE = 64 * 1024  // 64KB
    const start = state.position
    const bytesToRead = Math.min(size - start, MAX_READ_SIZE)
    const stream = fs.createReadStream(logPath, { start, end: start + bytesToRead - 1 })
    stream.on('error', () => {})

    const chunks: Buffer[] = []
    stream.on('data', (chunk) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
    })
    stream.on('end', () => {
      state.position = start + bytesToRead
      const callback = this.callbacks.get(logPath)
      if (!callback) return

      const text  = Buffer.concat(chunks).toString('utf-8')
      const lines = text.split('\n')

      // Emit every complete line; ignore the trailing empty fragment after the
      // last newline (it will be emitted once the next chunk arrives).
      for (let i = 0; i < lines.length - 1; i++) {
        if (lines[i].length > 0) callback(lines[i])
      }
    })
  }
}
