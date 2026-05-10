/**
 * Unit tests for workspace-store.ts
 *
 * Dependencies (electron app, fs, crypto) are mocked so tests run in plain
 * Node without a real Electron context.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mocks (hoisted before imports) ───────────────────────────────────────────

const { mockGetPath, mockReadFileSync, mockWriteFileSync } = vi.hoisted(() => ({
  mockGetPath:     vi.fn(() => '/mock/userData'),
  mockReadFileSync:  vi.fn(),
  mockWriteFileSync: vi.fn(),
}))

vi.mock('electron', () => ({
  app: { getPath: mockGetPath },
}))

vi.mock('fs', () => ({
  readFileSync:  (...args: unknown[]) => mockReadFileSync(...args),
  writeFileSync: (...args: unknown[]) => mockWriteFileSync(...args),
}))

let uuidCounter = 0
vi.mock('crypto', () => ({
  randomUUID: () => `uuid-${++uuidCounter}`,
}))

// ── Imports after mocks ───────────────────────────────────────────────────────

import { loadWorkspaces, saveWorkspaces, getActiveProject } from '../workspace-store'
import type { WorkspaceData } from '../workspace-store'

// ── Helpers ───────────────────────────────────────────────────────────────────

const STORAGE_PATH = '/mock/userData/workspaces.json'

function makeData(overrides: Partial<WorkspaceData> = {}): WorkspaceData {
  return {
    groups: [],
    activeGroupId: null,
    activeProjectPath: null,
    ...overrides,
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('workspace-store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    uuidCounter = 0
  })

  describe('loadWorkspaces()', () => {
    it('returns persisted data when the file exists and is valid', () => {
      const stored: WorkspaceData = makeData({
        groups: [{ id: 'g1', name: 'Work', iconLetter: 'W', projects: [] }],
        activeGroupId: 'g1',
        activeProjectPath: '/some/project',
      })
      mockReadFileSync.mockReturnValue(JSON.stringify(stored))

      const result = loadWorkspaces()

      expect(result).toEqual(stored)
      expect(mockReadFileSync).toHaveBeenCalledWith(STORAGE_PATH, 'utf-8')
    })

    it('creates a default group on first launch when file is missing', () => {
      mockReadFileSync.mockImplementation(() => {
        throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' })
      })

      const result = loadWorkspaces()

      expect(result.groups).toHaveLength(1)
      expect(result.groups[0].name).toBe('Projects')
      expect(result.groups[0].iconLetter).toBe('P')
      expect(result.groups[0].projects).toHaveLength(1)
      expect(result.groups[0].projects[0].path).toBe(process.cwd())
      expect(result.activeGroupId).toBe(result.groups[0].id)
      expect(result.activeProjectPath).toBe(process.cwd())
    })

    it('saves default data to disk on first launch', () => {
      mockReadFileSync.mockImplementation(() => { throw new Error('ENOENT') })

      loadWorkspaces()

      expect(mockWriteFileSync).toHaveBeenCalledWith(
        STORAGE_PATH,
        expect.any(String),
        'utf-8',
      )
    })

    it('falls back to default when file contains malformed JSON', () => {
      mockReadFileSync.mockReturnValue('{ not valid json }')

      const result = loadWorkspaces()

      expect(result.groups).toHaveLength(1)
      expect(result.groups[0].name).toBe('Projects')
    })

    it('falls back to default when file parses but groups is not an array', () => {
      mockReadFileSync.mockReturnValue(JSON.stringify({ groups: 'oops' }))

      const result = loadWorkspaces()

      expect(result.groups).toHaveLength(1)
    })
  })

  describe('saveWorkspaces()', () => {
    it('writes JSON to the expected storage path', () => {
      const data = makeData({ activeGroupId: 'g1' })

      saveWorkspaces(data)

      expect(mockWriteFileSync).toHaveBeenCalledWith(
        STORAGE_PATH,
        JSON.stringify(data, null, 2),
        'utf-8',
      )
    })
  })

  describe('getActiveProject()', () => {
    it('returns null when activeProjectPath is null', () => {
      mockReadFileSync.mockReturnValue(JSON.stringify(makeData({ activeProjectPath: null })))

      expect(getActiveProject()).toBeNull()
    })

    it('returns the active project path when set', () => {
      mockReadFileSync.mockReturnValue(
        JSON.stringify(makeData({ activeProjectPath: '/users/tom/myproject' }))
      )

      expect(getActiveProject()).toBe('/users/tom/myproject')
    })
  })
})
