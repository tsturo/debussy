/**
 * Unit tests for conductor-bridge.ts
 *
 * ConductorBridge depends on electron (BrowserWindow), child_process (spawn),
 * and fs (readFileSync), all of which are mocked so the tests run in a plain
 * Node environment without Electron.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { EventEmitter } from 'events'
import type { ChildProcess } from 'child_process'

// ── Mocks (hoisted before imports) ───────────────────────────────────────────

const mockSend = vi.fn()

vi.mock('electron', () => ({
  BrowserWindow: {
    getAllWindows: () => [{ webContents: { send: mockSend } }],
  },
}))

vi.mock('child_process', () => ({
  spawn: vi.fn(),
}))

vi.mock('fs', () => ({
  readFileSync: vi.fn(),
  writeFileSync: vi.fn(),
  unlinkSync: vi.fn(),
}))

// ── Imports after mocks ───────────────────────────────────────────────────────

import { ConductorBridge } from '../conductor-bridge'
import { IPC } from '../../shared/ipc-channels'
import { spawn } from 'child_process'
import { readFileSync } from 'fs'

// ── Helpers ───────────────────────────────────────────────────────────────────

/** A fake ChildProcess with a controllable stdout emitter and a kill spy. */
type MockProcess = EventEmitter & {
  stdout: EventEmitter
  kill: ReturnType<typeof vi.fn>
}

function createMockProcess(): MockProcess {
  const proc = new EventEmitter() as MockProcess
  proc.stdout = new EventEmitter()
  proc.kill = vi.fn()
  return proc
}

const spawnMock     = vi.mocked(spawn)
const readFileMock  = vi.mocked(readFileSync)

// ── Test suite ────────────────────────────────────────────────────────────────

describe('ConductorBridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default: reading conductor.md succeeds; config.json returns a model
    readFileMock.mockImplementation((filePath: unknown) => {
      const p = String(filePath)
      if (p.includes('conductor.md')) return 'system prompt content'
      if (p.includes('config.json')) return '{"role_models":{"conductor":"claude-test-model"}}'
      throw Object.assign(new Error(`ENOENT: ${p}`), { code: 'ENOENT' })
    })
  })

  it('spawns claude CLI with the conductor system prompt and configured model', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage({ text: 'hello world' }, '/project')

    expect(spawnMock).toHaveBeenCalledWith(
      'claude',
      ['--print', '--session-id', expect.any(String), '--system-prompt', 'system prompt content', '--model', 'claude-test-model', 'hello world'],
      expect.objectContaining({ cwd: '/project' }),
    )
  })

  it('defaults to claude-sonnet-4-6 when no role_models config is present', () => {
    readFileMock.mockImplementation((filePath: unknown) => {
      const p = String(filePath)
      if (p.includes('conductor.md')) return 'system prompt'
      throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' })
    })
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('hi', '/project')

    expect(spawnMock).toHaveBeenCalledWith(
      'claude',
      expect.arrayContaining(['--model', 'claude-sonnet-4-6']),
      expect.any(Object),
    )
  })

  it('streams stdout chunks to the renderer via CONDUCTOR_RESPONSE_CHUNK', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    proc.stdout.emit('data', Buffer.from('chunk one'))
    proc.stdout.emit('data', Buffer.from('chunk two'))

    expect(mockSend).toHaveBeenCalledWith(IPC.CONDUCTOR_RESPONSE_CHUNK, 'chunk one')
    expect(mockSend).toHaveBeenCalledWith(IPC.CONDUCTOR_RESPONSE_CHUNK, 'chunk two')
  })

  it('sends CONDUCTOR_RESPONSE_DONE on normal (non-signal) process exit', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    proc.emit('close', 0, null)

    expect(mockSend).toHaveBeenCalledWith(IPC.CONDUCTOR_RESPONSE_DONE, null)
  })

  it('does NOT send CONDUCTOR_RESPONSE_DONE when process exits via SIGTERM', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    proc.emit('close', null, 'SIGTERM')

    const doneCalls = mockSend.mock.calls.filter(([ch]) => ch === IPC.CONDUCTOR_RESPONSE_DONE)
    expect(doneCalls).toHaveLength(0)
  })

  it('does NOT send CONDUCTOR_RESPONSE_DONE when process exits via SIGKILL', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    proc.emit('close', null, 'SIGKILL')

    const doneCalls = mockSend.mock.calls.filter(([ch]) => ch === IPC.CONDUCTOR_RESPONSE_DONE)
    expect(doneCalls).toHaveLength(0)
  })

  it('cancelCurrent kills the active process', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    bridge.cancelCurrent()

    expect(proc.kill).toHaveBeenCalled()
  })

  it('cancelCurrent is a no-op when no process is running', () => {
    const bridge = new ConductorBridge()
    expect(() => bridge.cancelCurrent()).not.toThrow()
  })

  it('shows a helpful error message in chat when claude CLI is not found (ENOENT)', () => {
    const proc = createMockProcess()
    spawnMock.mockReturnValue(proc as unknown as ChildProcess)
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')
    const err = Object.assign(new Error('spawn claude ENOENT'), { code: 'ENOENT' }) as NodeJS.ErrnoException
    proc.emit('error', err)

    const chunkCalls = mockSend.mock.calls.filter(([ch]) => ch === IPC.CONDUCTOR_RESPONSE_CHUNK)
    expect(chunkCalls.length).toBeGreaterThan(0)
    expect(chunkCalls[0][1]).toMatch(/claude CLI not found/i)
    expect(mockSend).toHaveBeenCalledWith(IPC.CONDUCTOR_RESPONSE_DONE, null)
  })

  it('shows error in chat when conductor prompt file is missing', () => {
    readFileMock.mockImplementation(() => {
      throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' })
    })
    const bridge = new ConductorBridge()

    bridge.sendMessage('msg', '/project')

    // Should not spawn any process
    expect(spawnMock).not.toHaveBeenCalled()
    // Should broadcast an error chunk and done
    const chunkCalls = mockSend.mock.calls.filter(([ch]) => ch === IPC.CONDUCTOR_RESPONSE_CHUNK)
    expect(chunkCalls.length).toBeGreaterThan(0)
    expect(chunkCalls[0][1]).toMatch(/Error/i)
    expect(mockSend).toHaveBeenCalledWith(IPC.CONDUCTOR_RESPONSE_DONE, null)
  })

  // ── Race condition fix ────────────────────────────────────────────────────

  it('old process close event does not null out the new process (race condition fix)', () => {
    const proc1 = createMockProcess()
    const proc2 = createMockProcess()
    spawnMock
      .mockReturnValueOnce(proc1 as unknown as ChildProcess)
      .mockReturnValueOnce(proc2 as unknown as ChildProcess)

    const bridge = new ConductorBridge()

    // Start first message — proc1 is active
    bridge.sendMessage('first', '/project')

    // Start second message — cancelCurrent kills proc1, proc2 becomes active
    bridge.sendMessage('second', '/project')

    // proc1's close event fires asynchronously after being killed
    proc1.emit('close', null, 'SIGTERM')

    // The bridge still holds proc2 — cancel should kill it
    bridge.cancelCurrent()
    expect(proc2.kill).toHaveBeenCalled()
  })

  it('old process error event does not null out the new process (race condition fix)', () => {
    const proc1 = createMockProcess()
    const proc2 = createMockProcess()
    spawnMock
      .mockReturnValueOnce(proc1 as unknown as ChildProcess)
      .mockReturnValueOnce(proc2 as unknown as ChildProcess)

    const bridge = new ConductorBridge()

    bridge.sendMessage('first', '/project')
    bridge.sendMessage('second', '/project')

    // proc1's error fires after proc2 is already active
    const err = Object.assign(new Error('something'), { code: 'EIO' }) as NodeJS.ErrnoException
    proc1.emit('error', err)

    // proc2 is still tracked — cancel kills it
    bridge.cancelCurrent()
    expect(proc2.kill).toHaveBeenCalled()
  })
})
