/**
 * Unit tests for db-reader.ts.
 *
 * Creates a temporary SQLite database with the takt schema, inserts known
 * test data, and verifies every exported function.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import Database from 'better-sqlite3'
import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'

import {
  openDatabase,
  closeDatabase,
  listTasks,
  getTask,
  getTaskDeps,
  getTaskLog,
  listProjects,
} from '../db-reader'

// ── Schema (mirrors src/debussy/takt/db.py SCHEMA_SQL) ───────────────────────

const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS metadata (
     key   TEXT PRIMARY KEY,
     value TEXT NOT NULL
   )`,
  `CREATE TABLE IF NOT EXISTS tasks (
     id              TEXT PRIMARY KEY,
     seq             INTEGER NOT NULL,
     title           TEXT NOT NULL,
     description     TEXT DEFAULT '',
     stage           TEXT DEFAULT 'backlog',
     status          TEXT DEFAULT 'pending',
     tags            TEXT DEFAULT '[]',
     rejection_count INTEGER DEFAULT 0,
     created_at      TEXT DEFAULT (datetime('now')),
     updated_at      TEXT DEFAULT (datetime('now'))
   )`,
  `CREATE TABLE IF NOT EXISTS dependencies (
     task_id       TEXT REFERENCES tasks(id),
     depends_on_id TEXT REFERENCES tasks(id),
     PRIMARY KEY (task_id, depends_on_id)
   )`,
  `CREATE TABLE IF NOT EXISTS log (
     id        INTEGER PRIMARY KEY AUTOINCREMENT,
     task_id   TEXT REFERENCES tasks(id),
     timestamp TEXT DEFAULT (datetime('now')),
     type      TEXT,
     author    TEXT,
     message   TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS projects (
     prefix     TEXT PRIMARY KEY,
     name       TEXT NOT NULL,
     is_default INTEGER NOT NULL DEFAULT 0,
     next_seq   INTEGER NOT NULL DEFAULT 1
   )`,
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildTestDb(): { db: Database.Database; dbPath: string } {
  const dbPath = path.join(
    os.tmpdir(),
    `takt-test-${Date.now()}-${Math.floor(Math.random() * 1e6)}.db`
  )
  const rw = new Database(dbPath)

  for (const stmt of SCHEMA_STATEMENTS) {
    rw.exec(stmt)
  }

  // 3 tasks
  const insertTask = rw.prepare(
    `INSERT INTO tasks (id, seq, title, description, stage, status, tags,
                        rejection_count, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
  insertTask.run('DBS-1', 1, 'First task',  'Desc 1', 'backlog',     'pending', '["backend"]',       0, '2026-01-01 10:00:00', '2026-01-01 10:00:00')
  insertTask.run('DBS-2', 2, 'Second task', 'Desc 2', 'development', 'active',  '["frontend","ui"]', 1, '2026-01-02 10:00:00', '2026-01-02 10:00:00')
  insertTask.run('DBS-3', 3, 'Third task',  'Desc 3', 'done',        'pending', '[]',                0, '2026-01-03 10:00:00', '2026-01-03 10:00:00')

  // 1 dependency: DBS-2 depends on DBS-1
  rw.prepare(`INSERT INTO dependencies (task_id, depends_on_id) VALUES (?, ?)`).run('DBS-2', 'DBS-1')

  // 2 log entries for DBS-1 — inserted in reverse order to validate chrono sort
  rw.prepare(
    `INSERT INTO log (task_id, timestamp, type, author, message) VALUES (?, ?, ?, ?, ?)`
  ).run('DBS-1', '2026-01-01 11:00:00', 'transition', 'watcher',   'moved to backlog')
  rw.prepare(
    `INSERT INTO log (task_id, timestamp, type, author, message) VALUES (?, ?, ?, ?, ?)`
  ).run('DBS-1', '2026-01-01 10:00:00', 'comment',    'conductor', 'created')

  // 1 project
  rw.prepare(
    `INSERT INTO projects (prefix, name, is_default, next_seq) VALUES (?, ?, ?, ?)`
  ).run('DBS', 'Debussy', 1, 4)

  rw.close()

  // Re-open read-only so the test suite exercises the production code path
  return { db: new Database(dbPath, { readonly: true }), dbPath }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('db-reader', () => {
  let db: Database.Database
  let dbPath: string

  beforeAll(() => {
    const result = buildTestDb()
    db = result.db
    dbPath = result.dbPath
  })

  afterAll(() => {
    closeDatabase(db)
    if (fs.existsSync(dbPath)) {
      fs.unlinkSync(dbPath)
    }
  })

  // openDatabase -----------------------------------------------------------

  describe('openDatabase', () => {
    it('opens a real database file', () => {
      const handle = openDatabase(dbPath)
      expect(handle).not.toBeNull()
      closeDatabase(handle)
    })

    it('opens in read-only mode — writes throw', () => {
      const handle = openDatabase(dbPath)
      expect(handle).not.toBeNull()
      expect(() =>
        handle!.prepare(`INSERT INTO tasks (id, seq, title) VALUES ('X', 99, 'X')`).run()
      ).toThrow()
      closeDatabase(handle)
    })
  })

  // listTasks ---------------------------------------------------------------

  describe('listTasks', () => {
    it('returns all 3 tasks', () => {
      expect(listTasks(db)).toHaveLength(3)
    })

    it('returns empty array when db is null', () => {
      expect(listTasks(null)).toEqual([])
    })

    it('parses tags from JSON string to string[]', () => {
      const tasks = listTasks(db)
      const t1 = tasks.find((t) => t.id === 'DBS-1')!
      const t2 = tasks.find((t) => t.id === 'DBS-2')!
      const t3 = tasks.find((t) => t.id === 'DBS-3')!
      expect(t1.tags).toEqual(['backend'])
      expect(t2.tags).toEqual(['frontend', 'ui'])
      expect(t3.tags).toEqual([])
    })

    it('returns tasks with correct schema field types', () => {
      const t = listTasks(db)[0]
      expect(typeof t.id).toBe('string')
      expect(typeof t.seq).toBe('number')
      expect(typeof t.title).toBe('string')
      expect(typeof t.description).toBe('string')
      expect(typeof t.stage).toBe('string')
      expect(typeof t.status).toBe('string')
      expect(Array.isArray(t.tags)).toBe(true)
      expect(typeof t.rejection_count).toBe('number')
      expect(typeof t.created_at).toBe('string')
      expect(typeof t.updated_at).toBe('string')
    })
  })

  // getTask -----------------------------------------------------------------

  describe('getTask', () => {
    it('returns the correct task', () => {
      const task = getTask(db, 'DBS-2')
      expect(task).not.toBeNull()
      expect(task!.id).toBe('DBS-2')
      expect(task!.title).toBe('Second task')
      expect(task!.stage).toBe('development')
      expect(task!.status).toBe('active')
      expect(task!.rejection_count).toBe(1)
    })

    it('parses tags correctly', () => {
      const task = getTask(db, 'DBS-2')!
      expect(task.tags).toEqual(['frontend', 'ui'])
    })

    it('returns null for unknown id', () => {
      expect(getTask(db, 'NOPE-99')).toBeNull()
    })

    it('returns null when db is null', () => {
      expect(getTask(null, 'DBS-1')).toBeNull()
    })
  })

  // getTaskDeps -------------------------------------------------------------

  describe('getTaskDeps', () => {
    it('returns the dependency for DBS-2', () => {
      const deps = getTaskDeps(db, 'DBS-2')
      expect(deps).toHaveLength(1)
      expect(deps[0].task_id).toBe('DBS-2')
      expect(deps[0].depends_on_id).toBe('DBS-1')
    })

    it('returns empty array for a task with no deps', () => {
      expect(getTaskDeps(db, 'DBS-1')).toEqual([])
    })

    it('returns empty array when db is null', () => {
      expect(getTaskDeps(null, 'DBS-2')).toEqual([])
    })
  })

  // getTaskLog --------------------------------------------------------------

  describe('getTaskLog', () => {
    it('returns entries in chronological order', () => {
      const entries = getTaskLog(db, 'DBS-1')
      expect(entries).toHaveLength(2)
      expect(entries[0].timestamp).toBe('2026-01-01 10:00:00')
      expect(entries[0].message).toBe('created')
      expect(entries[1].timestamp).toBe('2026-01-01 11:00:00')
      expect(entries[1].message).toBe('moved to backlog')
    })

    it('returns empty array for a task with no log', () => {
      expect(getTaskLog(db, 'DBS-3')).toEqual([])
    })

    it('returns empty array when db is null', () => {
      expect(getTaskLog(null, 'DBS-1')).toEqual([])
    })
  })

  // listProjects ------------------------------------------------------------

  describe('listProjects', () => {
    it('returns the project with correct fields', () => {
      const projects = listProjects(db)
      expect(projects).toHaveLength(1)
      expect(projects[0].prefix).toBe('DBS')
      expect(projects[0].name).toBe('Debussy')
      expect(projects[0].is_default).toBe(true)
      expect(projects[0].next_seq).toBe(4)
    })

    it('returns empty array when db is null', () => {
      expect(listProjects(null)).toEqual([])
    })
  })

  // Null-db safety (consolidated) ------------------------------------------

  describe('null db — all functions return empty/null', () => {
    it('all functions handle null gracefully', () => {
      expect(listTasks(null)).toEqual([])
      expect(getTask(null, 'X')).toBeNull()
      expect(getTaskDeps(null, 'X')).toEqual([])
      expect(getTaskLog(null, 'X')).toEqual([])
      expect(listProjects(null)).toEqual([])
    })
  })
})
