/**
 * Read-only SQLite reader for the takt database (.takt/takt.db).
 *
 * Opens the database in READ-ONLY mode to avoid WAL write contention
 * with the watcher and agents.  All functions accept a nullable Database
 * handle and return empty arrays / null when the DB is not available.
 */

import Database from 'better-sqlite3'
import type { Task, Dependency, LogEntry } from '../shared/types'

export type { Task, Dependency, LogEntry }

export interface Project {
  prefix: string
  name: string
  is_default: boolean
  next_seq: number
}

/**
 * Open the takt database at the given path in read-only mode.
 * Returns null if the file does not exist yet (no DB is a valid state).
 */
export function openDatabase(dbPath: string): Database.Database | null {
  try {
    return new Database(dbPath, { readonly: true, fileMustExist: false })
  } catch {
    // fileMustExist: false means this should never throw for a missing file,
    // but better-sqlite3 may still throw if the path is a directory, etc.
    return null
  }
}

/** Close the database connection.  No-ops if db is null. */
export function closeDatabase(db: Database.Database | null): void {
  db?.close()
}

/** Return all tasks, with the tags JSON column parsed into string[]. */
export function listTasks(db: Database.Database | null): Task[] {
  if (!db) return []
  const rows = db
    .prepare(
      `SELECT id, seq, title, description, stage, status, tags,
              rejection_count, created_at, updated_at
       FROM tasks
       ORDER BY seq`
    )
    .all() as Array<Omit<Task, 'tags'> & { tags: string }>
  return rows.map(parseTask)
}

/** Return a single task by id, or null if not found. */
export function getTask(db: Database.Database | null, id: string): Task | null {
  if (!db) return null
  const row = db
    .prepare(
      `SELECT id, seq, title, description, stage, status, tags,
              rejection_count, created_at, updated_at
       FROM tasks WHERE id = ?`
    )
    .get(id) as (Omit<Task, 'tags'> & { tags: string }) | undefined
  return row ? parseTask(row) : null
}

/** Return all dependency rows for a task. */
export function getTaskDeps(db: Database.Database | null, id: string): Dependency[] {
  if (!db) return []
  return db
    .prepare(`SELECT task_id, depends_on_id FROM dependencies WHERE task_id = ?`)
    .all(id) as Dependency[]
}

/** Return log entries for a task in chronological order. */
export function getTaskLog(db: Database.Database | null, id: string): LogEntry[] {
  if (!db) return []
  return db
    .prepare(
      `SELECT id, task_id, timestamp, type, author, message
       FROM log WHERE task_id = ? ORDER BY timestamp ASC, id ASC`
    )
    .all(id) as LogEntry[]
}

/** Return all projects. */
export function listProjects(db: Database.Database | null): Project[] {
  if (!db) return []
  const rows = db
    .prepare(`SELECT prefix, name, is_default, next_seq FROM projects`)
    .all() as Array<{ prefix: string; name: string; is_default: number; next_seq: number }>
  return rows.map((r) => ({ ...r, is_default: r.is_default === 1 }))
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function parseTask(row: Omit<Task, 'tags'> & { tags: string }): Task {
  let tags: string[] = []
  try {
    const parsed = JSON.parse(row.tags)
    if (Array.isArray(parsed)) tags = parsed
  } catch {
    // malformed JSON — treat as empty
  }
  return { ...row, tags }
}
