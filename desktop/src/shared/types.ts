// Shared TypeScript types for the Debussy Electron app.
// These types mirror the SQLite schema (takt/db.py), watcher state format
// (watcher.py save_state), and config keys (config.py KNOWN_KEYS).

// ── Pipeline stage and status ────────────────────────────────────────────────

export type Stage =
  | 'backlog'
  | 'development'
  | 'reviewing'
  | 'security_review'
  | 'merging'
  | 'acceptance'
  | 'done'

export type Status = 'pending' | 'active' | 'blocked'

// ── DB-backed types ──────────────────────────────────────────────────────────

/** Matches the `tasks` table in takt/db.py */
export interface Task {
  id: string           // e.g. "DBS-1"
  seq: number
  title: string
  description: string
  stage: Stage
  status: Status
  tags: string[]       // parsed from JSON text stored in the DB
  rejection_count: number
  created_at: string   // ISO timestamp
  updated_at: string   // ISO timestamp
}

/** Matches the `dependencies` table in takt/db.py */
export interface Dependency {
  task_id: string
  depends_on_id: string
}

/** Matches the `log` table in takt/db.py */
export type LogType = 'comment' | 'transition' | 'assignment'

export interface LogEntry {
  id: number
  task_id: string
  timestamp: string    // ISO timestamp
  type: LogType
  author: string
  message: string
}

// ── Watcher state (watcher_state.json) ──────────────────────────────────────

export type AgentRole =
  | 'developer'
  | 'reviewer'
  | 'integrator'
  | 'tester'
  | 'security-reviewer'

/**
 * Matches the per-task entries written by watcher.py save_state().
 * Field names correspond exactly to the JSON keys in watcher_state.json:
 *   agent        → agent.name
 *   role         → agent.role
 *   log          → agent.log_path
 *   tmux         → agent.tmux
 *   worktree_path→ agent.worktree_path
 *   started_at   → agent.started_at (Unix timestamp float)
 *   pid          → agent.proc.pid (omitted when proc is None)
 */
export interface AgentInfo {
  agent: string          // e.g. "developer-bach"
  role: AgentRole
  log: string            // e.g. ".debussy/logs/developer-bach.log"
  tmux: boolean
  worktree_path: string
  started_at: number     // Unix timestamp (float serialised as number)
  pid?: number           // absent when the agent has no subprocess
}

/** watcher_state.json top-level structure: keyed by task_id */
export type WatcherState = Record<string, AgentInfo>

// ── Debussy configuration (config.py KNOWN_KEYS) ────────────────────────────

/**
 * All 14 known config keys from config.py KNOWN_KEYS / DEFAULTS.
 * Keys that have no DEFAULTS entry are nullable (may be absent in config.json).
 */
export interface DebussyConfig {
  max_total_agents: number                // default 8
  use_tmux_windows: boolean               // default false
  base_branch: string | null
  paused: boolean                         // default false
  agent_timeout: number                   // default 3600 seconds
  agent_provider: string                  // default "claude"
  role_models: Record<string, string>     // role → model string
  docs_path: string | null
  notify_conductor: boolean               // default false
  max_role_agents: Record<string, number> // role → max concurrent count
  monitor_interval: number                // default 240
  project_type: 'web' | 'ios' | null
  conductor_session_id: string | null
  test_command: string | null
  auto_start_watcher: boolean             // default false — UI-only workspace field
}

// ── UI-only types (not backed by DB) ────────────────────────────────────────

export interface ConductorMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface WorkspaceGroup {
  id: string
  name: string
  icon_letter: string
}

export interface ProjectEntry {
  path: string
  name: string
  group_id: string
}
