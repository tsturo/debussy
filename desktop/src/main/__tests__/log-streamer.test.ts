/**
 * Unit tests for log-streamer.ts
 *
 * Tests use real file I/O in a temporary directory so that fs.watch()
 * behaviour can be exercised end-to-end.  Each test cleans up after itself.
 *
 * Note: a small delay (WATCH_SETTLE_MS) is required between calling
 * startTailing() and writing to the file to allow the OS watcher to register
 * before the first change event can be emitted.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'

import { LogStreamer } from '../log-streamer'

// Time to let fs.watch() register with the OS before we write
const WATCH_SETTLE_MS = 150

// Helper: wait up to `ms` milliseconds for `predicate` to become true
async function waitFor(predicate: () => boolean, ms = 2000): Promise<void> {
  const start = Date.now()
  while (!predicate()) {
    if (Date.now() - start > ms) throw new Error('waitFor timed out')
    await new Promise((r) => setTimeout(r, 20))
  }
}

// ── Test setup ────────────────────────────────────────────────────────────────

let tmpDir: string
let streamer: LogStreamer

beforeEach(() => {
  tmpDir   = fs.mkdtempSync(path.join(os.tmpdir(), 'log-streamer-test-'))
  streamer = new LogStreamer()
})

afterEach(() => {
  streamer.stopAll()
  fs.rmSync(tmpDir, { recursive: true, force: true })
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('LogStreamer', () => {
  it('triggers callback with new lines appended to an existing file', async () => {
    const logPath = path.join(tmpDir, 'agent.log')
    fs.writeFileSync(logPath, '')

    const received: string[] = []
    streamer.startTailing(logPath, (line) => received.push(line))

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.appendFileSync(logPath, 'first line\nsecond line\n')

    await waitFor(() => received.length >= 2)
    expect(received).toContain('first line')
    expect(received).toContain('second line')
  })

  it('does not emit content that was already present before tailing started', async () => {
    const logPath = path.join(tmpDir, 'agent.log')
    fs.writeFileSync(logPath, 'old line\n')

    const received: string[] = []
    streamer.startTailing(logPath, (line) => received.push(line))

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.appendFileSync(logPath, 'new line\n')

    await waitFor(() => received.length >= 1)
    expect(received).not.toContain('old line')
    expect(received).toContain('new line')
  })

  it('handles a missing file gracefully and picks up lines once it is created', async () => {
    const logPath = path.join(tmpDir, 'missing.log')
    // File does NOT exist yet

    const received: string[] = []
    streamer.startTailing(logPath, (line) => received.push(line))

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.writeFileSync(logPath, 'appeared line\n')

    await waitFor(() => received.length >= 1, 3000)
    expect(received).toContain('appeared line')
  })

  it('resets position on file truncation', async () => {
    const logPath = path.join(tmpDir, 'agent.log')
    // Write enough content so the position is large
    fs.writeFileSync(logPath, 'a'.repeat(200) + '\n')

    const received: string[] = []
    streamer.startTailing(logPath, (line) => received.push(line))

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    // Overwrite with shorter content — position (201) > new size (6)
    fs.writeFileSync(logPath, 'short\n')

    await waitFor(() => received.includes('short'), 3000)
    expect(received).toContain('short')
  })

  it('stopTailing stops callbacks from firing', async () => {
    const logPath = path.join(tmpDir, 'agent.log')
    fs.writeFileSync(logPath, '')

    const received: string[] = []
    streamer.startTailing(logPath, (line) => received.push(line))
    streamer.stopTailing(logPath)

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.appendFileSync(logPath, 'should not appear\n')

    await new Promise((r) => setTimeout(r, 300))
    expect(received).toHaveLength(0)
  })

  it('stopAll cleans up all active watchers', async () => {
    const logA = path.join(tmpDir, 'a.log')
    const logB = path.join(tmpDir, 'b.log')
    fs.writeFileSync(logA, '')
    fs.writeFileSync(logB, '')

    const receivedA: string[] = []
    const receivedB: string[] = []
    streamer.startTailing(logA, (l) => receivedA.push(l))
    streamer.startTailing(logB, (l) => receivedB.push(l))

    streamer.stopAll()

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.appendFileSync(logA, 'line-a\n')
    fs.appendFileSync(logB, 'line-b\n')

    await new Promise((r) => setTimeout(r, 300))
    expect(receivedA).toHaveLength(0)
    expect(receivedB).toHaveLength(0)
  })

  it('re-starting tailing on the same path replaces the old callback', async () => {
    const logPath = path.join(tmpDir, 'agent.log')
    fs.writeFileSync(logPath, '')

    const first:  string[] = []
    const second: string[] = []

    streamer.startTailing(logPath, (l) => first.push(l))
    // Restart with a different callback — allow settle after restart
    streamer.startTailing(logPath, (l) => second.push(l))

    await new Promise((r) => setTimeout(r, WATCH_SETTLE_MS))
    fs.appendFileSync(logPath, 'only second\n')

    await waitFor(() => second.length >= 1)
    expect(first).toHaveLength(0)
    expect(second).toContain('only second')
  })
})
