/**
 * Workspace groups storage.
 *
 * Persists workspace groups (each containing a list of project paths) to
 * {userData}/workspaces.json using Electron's app.getPath('userData').
 */

import { app } from 'electron'
import { join, basename } from 'path'
import { randomUUID } from 'crypto'
import * as fs from 'fs'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface WorkspaceProject {
  path: string   // absolute path to the project directory
  name: string   // display name (basename of path)
}

export interface WorkspaceGroup {
  id: string         // uuid
  name: string       // e.g. "Work @ Visma"
  iconLetter: string // e.g. "V"
  projects: WorkspaceProject[]
}

export interface WorkspaceData {
  groups: WorkspaceGroup[]
  activeGroupId: string | null
  activeProjectPath: string | null
}

// ── Storage path ──────────────────────────────────────────────────────────────

function storagePath(): string {
  return join(app.getPath('userData'), 'workspaces.json')
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Load workspace data from disk.
 * On first launch (file absent or unreadable), creates a default group
 * containing the current working directory as its first project.
 */
export function loadWorkspaces(): WorkspaceData {
  try {
    const raw = fs.readFileSync(storagePath(), 'utf-8')
    const parsed = JSON.parse(raw) as WorkspaceData
    if (parsed && Array.isArray(parsed.groups)) return parsed
  } catch {
    // file missing or malformed — fall through to default
  }

  const cwd = process.cwd()
  const defaultGroup: WorkspaceGroup = {
    id: randomUUID(),
    name: 'Projects',
    iconLetter: 'P',
    projects: [{ path: cwd, name: basename(cwd) }],
  }
  const data: WorkspaceData = {
    groups: [defaultGroup],
    activeGroupId: defaultGroup.id,
    activeProjectPath: cwd,
  }
  saveWorkspaces(data)
  return data
}

/** Persist workspace data to disk. */
export function saveWorkspaces(data: WorkspaceData): void {
  fs.writeFileSync(storagePath(), JSON.stringify(data, null, 2), 'utf-8')
}

/**
 * Return the active project path, or null if no project is active.
 * Reads directly from disk so callers always see the latest value.
 */
export function getActiveProject(): string | null {
  return loadWorkspaces().activeProjectPath
}
