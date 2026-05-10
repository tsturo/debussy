/**
 * Mock data for the Debussy Electron UI.
 * Used in App.tsx while real IPC data loading (DBS-17) is pending.
 */

import type { Task, LogEntry, AgentRole, Stage, ConductorMessage } from '../../shared/types'

// ── Tasks (8 across all stages) ───────────────────────────────────────────────

const NOW = new Date()

function isoMinsAgo(mins: number): string {
  return new Date(NOW.getTime() - mins * 60_000).toISOString()
}

export const MOCK_TASKS: Task[] = [
  {
    id: 'DBS-1',
    seq: 1,
    title: 'User model and DB migration',
    description:
      'Create the User Pydantic schema and Alembic migration.\n\n' +
      'Fields: id, email, password_hash, created_at, updated_at\n' +
      'File: src/debussy/models/user.py\n\n' +
      'Run: alembic upgrade head after migration is generated.',
    stage: 'development',
    status: 'active',
    tags: [],
    rejection_count: 0,
    created_at: isoMinsAgo(120),
    updated_at: isoMinsAgo(35),
  },
  {
    id: 'DBS-2',
    seq: 2,
    title: 'Login endpoint POST /auth/login',
    description:
      'Implement the login endpoint.\n\n' +
      'Path: POST /auth/login\n' +
      'Body: { email, password }\n' +
      'Returns: { access_token, refresh_token }\n' +
      'File: src/debussy/routes/auth.py',
    stage: 'development',
    status: 'active',
    tags: [],
    rejection_count: 1,
    created_at: isoMinsAgo(115),
    updated_at: isoMinsAgo(20),
  },
  {
    id: 'DBS-3',
    seq: 3,
    title: 'JWT middleware and token validation',
    description:
      'Add FastAPI middleware that reads the Authorization header, validates\n' +
      'the JWT, and attaches the user to request.state.\n\n' +
      'File: src/debussy/middleware/auth.py\n' +
      'Uses: python-jose, passlib',
    stage: 'development',
    status: 'blocked',
    tags: ['security'],
    rejection_count: 2,
    created_at: isoMinsAgo(110),
    updated_at: isoMinsAgo(5),
  },
  {
    id: 'DBS-4',
    seq: 4,
    title: 'Password reset flow',
    description:
      'Implement forgot-password and reset-password endpoints.\n\n' +
      'POST /auth/forgot-password → emails a reset link\n' +
      'POST /auth/reset-password  → validates token and sets new password',
    stage: 'reviewing',
    status: 'active',
    tags: [],
    rejection_count: 0,
    created_at: isoMinsAgo(100),
    updated_at: isoMinsAgo(45),
  },
  {
    id: 'DBS-5',
    seq: 5,
    title: 'User profile API endpoints',
    description:
      'GET /users/me → current user profile\n' +
      'PATCH /users/me → update display name, avatar URL\n\n' +
      'File: src/debussy/routes/users.py',
    stage: 'merging',
    status: 'active',
    tags: [],
    rejection_count: 0,
    created_at: isoMinsAgo(90),
    updated_at: isoMinsAgo(12),
  },
  {
    id: 'DBS-6',
    seq: 6,
    title: 'OAuth2 Google provider',
    description:
      'Integrate Google OAuth2 via authlib.\n\n' +
      'Redirect URI: /auth/google/callback\n' +
      'Scope: openid, email, profile\n' +
      'File: src/debussy/routes/oauth.py',
    stage: 'done',
    status: 'pending',
    tags: [],
    rejection_count: 0,
    created_at: isoMinsAgo(200),
    updated_at: isoMinsAgo(80),
  },
  {
    id: 'DBS-7',
    seq: 7,
    title: 'Rate limiting middleware',
    description:
      'Apply slowapi rate limiting to auth endpoints:\n' +
      '  POST /auth/login     → 10 req/min per IP\n' +
      '  POST /auth/register  → 5 req/min per IP\n\n' +
      'File: src/debussy/middleware/rate_limit.py',
    stage: 'done',
    status: 'pending',
    tags: ['security'],
    rejection_count: 0,
    created_at: isoMinsAgo(180),
    updated_at: isoMinsAgo(75),
  },
  {
    id: 'DBS-8',
    seq: 8,
    title: 'Email verification on signup',
    description:
      'Send a verification email on registration.\n' +
      'Store a short-lived token in Redis with 24h TTL.\n' +
      'GET /auth/verify?token=... marks the account as verified.\n\n' +
      'File: src/debussy/routes/auth.py (extend existing)',
    stage: 'done',
    status: 'pending',
    tags: [],
    rejection_count: 0,
    created_at: isoMinsAgo(160),
    updated_at: isoMinsAgo(70),
  },
]

// ── Agents (4 active agents) ──────────────────────────────────────────────────

export const MOCK_AGENTS: Array<{
  taskId: string
  name: string
  role: AgentRole
  stage: Stage
  startedAt: number
}> = [
  {
    taskId: 'DBS-1',
    name: 'developer-bach',
    role: 'developer',
    stage: 'development',
    startedAt: Date.now() - 35 * 60_000,
  },
  {
    taskId: 'DBS-2',
    name: 'developer-mozart',
    role: 'developer',
    stage: 'development',
    startedAt: Date.now() - 20 * 60_000,
  },
  {
    taskId: 'DBS-4',
    name: 'reviewer-vivaldi',
    role: 'reviewer',
    stage: 'reviewing',
    startedAt: Date.now() - 45 * 60_000,
  },
  {
    taskId: 'DBS-5',
    name: 'integrator-strauss',
    role: 'integrator',
    stage: 'merging',
    startedAt: Date.now() - 12 * 60_000,
  },
]

// ── Conductor messages (6) ────────────────────────────────────────────────────

export const MOCK_CONDUCTOR_MESSAGES: ConductorMessage[] = [
  {
    id: 'cm-1',
    role: 'user',
    content: 'Create tasks for the auth system: user model, login, JWT middleware',
    timestamp: Date.now() - 90 * 60_000,
  },
  {
    id: 'cm-2',
    role: 'assistant',
    content:
      "Created 3 tasks and advanced them to development:\n" +
      "• DBS-1: User model and DB migration\n" +
      "• DBS-2: Login endpoint POST /auth/login\n" +
      "• DBS-3: JWT middleware and token validation\n" +
      "▸ takt create \"User model and DB migration\" -d \"...\"\n" +
      "▸ takt create \"Login endpoint POST /auth/login\" -d \"...\"\n" +
      "▸ takt create \"JWT middleware and token validation\" -d \"...\"\n" +
      "▸ takt advance DBS-1\n" +
      "▸ takt advance DBS-2\n" +
      "▸ takt advance DBS-3",
    timestamp: Date.now() - 88 * 60_000,
  },
  {
    id: 'cm-3',
    role: 'user',
    content: "DBS-3 keeps getting rejected — what's wrong?",
    timestamp: Date.now() - 30 * 60_000,
  },
  {
    id: 'cm-4',
    role: 'assistant',
    content:
      "The reviewer flagged a token refresh race condition — two simultaneous refresh requests can both succeed and generate conflicting tokens.\n\n" +
      "Fix: add a Redis lock around the refresh flow, or use a short-lived single-use refresh nonce.\n" +
      "▸ takt log DBS-3\n" +
      "▸ takt comment DBS-3 \"Add refresh lock before re-advancing\"",
    timestamp: Date.now() - 28 * 60_000,
  },
  {
    id: 'cm-5',
    role: 'user',
    content: "Got it. What's currently blocked?",
    timestamp: Date.now() - 10 * 60_000,
  },
  {
    id: 'cm-6',
    role: 'assistant',
    content:
      "DBS-3 is blocked pending the refresh lock fix (rejection_count=2). Everything else is healthy — DBS-4 is in reviewing, DBS-5 is merging, and DBS-6/7/8 are done.\n" +
      "▸ debussy board",
    timestamp: Date.now() - 8 * 60_000,
  },
]

// ── Log entries for DBS-1 (10 entries) ───────────────────────────────────────

export const MOCK_LOG_ENTRIES_BY_TASK: Record<string, LogEntry[]> = {
  'DBS-1': [
    {
      id: 1,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(118),
      type: 'transition',
      author: 'watcher',
      message: 'advanced backlog → development',
    },
    {
      id: 2,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(115),
      type: 'assignment',
      author: 'watcher',
      message: 'claimed by developer-bach',
    },
    {
      id: 3,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(110),
      type: 'comment',
      author: 'conductor',
      message: 'Make sure the migration is reversible (downgrade path required).',
    },
    {
      id: 4,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(100),
      type: 'transition',
      author: 'developer-bach',
      message: 'released — implementation complete',
    },
    {
      id: 5,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(99),
      type: 'transition',
      author: 'watcher',
      message: 'advanced development → reviewing',
    },
    {
      id: 6,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(95),
      type: 'assignment',
      author: 'watcher',
      message: 'claimed by reviewer-vivaldi',
    },
    {
      id: 7,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(80),
      type: 'transition',
      author: 'reviewer-vivaldi',
      message: 'rejected — missing downgrade migration',
    },
    {
      id: 8,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(78),
      type: 'transition',
      author: 'watcher',
      message: 'advanced reviewing → development (rework)',
    },
    {
      id: 9,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(40),
      type: 'assignment',
      author: 'watcher',
      message: 'claimed by developer-bach',
    },
    {
      id: 10,
      task_id: 'DBS-1',
      timestamp: isoMinsAgo(35),
      type: 'comment',
      author: 'developer-bach',
      message: 'Added downgrade path — drops the users table on rollback. Re-advancing.',
    },
  ],
  'DBS-2': [
    {
      id: 11,
      task_id: 'DBS-2',
      timestamp: isoMinsAgo(113),
      type: 'transition',
      author: 'watcher',
      message: 'advanced backlog → development',
    },
    {
      id: 12,
      task_id: 'DBS-2',
      timestamp: isoMinsAgo(110),
      type: 'assignment',
      author: 'watcher',
      message: 'claimed by developer-mozart',
    },
    {
      id: 13,
      task_id: 'DBS-2',
      timestamp: isoMinsAgo(22),
      type: 'transition',
      author: 'developer-mozart',
      message: 'rejected — bcrypt import error in CI',
    },
    {
      id: 14,
      task_id: 'DBS-2',
      timestamp: isoMinsAgo(20),
      type: 'assignment',
      author: 'watcher',
      message: 'claimed by developer-mozart',
    },
  ],
  'DBS-3': [
    {
      id: 20,
      task_id: 'DBS-3',
      timestamp: isoMinsAgo(108),
      type: 'transition',
      author: 'watcher',
      message: 'advanced backlog → development',
    },
    {
      id: 21,
      task_id: 'DBS-3',
      timestamp: isoMinsAgo(60),
      type: 'transition',
      author: 'watcher',
      message: 'rejected — refresh race condition',
    },
    {
      id: 22,
      task_id: 'DBS-3',
      timestamp: isoMinsAgo(28),
      type: 'comment',
      author: 'conductor',
      message: 'Add refresh lock before re-advancing',
    },
    {
      id: 23,
      task_id: 'DBS-3',
      timestamp: isoMinsAgo(5),
      type: 'transition',
      author: 'watcher',
      message: 'blocked — awaiting refresh lock fix',
    },
  ],
}

// ── Debussy config mock ───────────────────────────────────────────────────────

export const MOCK_CONFIG = {
  max_total_agents: 8,
  use_tmux_windows: false,
  base_branch: 'feature/auth-system',
  paused: false,
  agent_timeout: 3600,
  agent_provider: 'claude',
  role_models: {},
  docs_path: null,
  notify_conductor: false,
  max_role_agents: {},
  monitor_interval: 240,
  project_type: null,
  conductor_session_id: null,
  test_command: null,
}
