# Project Instructions

## Overview

This project uses takt (built-in SQLite) for task tracking. The watcher automatically spawns agents based on **stage** values on tasks.

---

## Core Principles

### 1. Think Before Coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them.
- If something is unclear, stop and ask.

### 2. Simplicity First

- No features beyond what was asked.
- No abstractions for single-use code.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

- Don't "improve" adjacent code.
- Match existing style.
- If you notice unrelated issues, file a task — don't fix silently.

### 4. Goal-Driven Execution

- Transform tasks into verifiable goals.
- Strong success criteria let you work independently.

---

## Pipeline Flow

Pipelines depending on task type:

```
Per task:      backlog → development → reviewing → merging → done
Security task: backlog → development → reviewing → security_review → merging → done
Per batch:     acceptance task (deps on all tasks) → acceptance → done
```

Tasks with the `security` tag (set by conductor) get routed through an extra security review after the standard code review. The watcher handles this conditionally.

Tasks with the `frontend` tag (set by conductor) trigger Playwright visual verification during development. The developer starts a dev server, takes screenshots, verifies visually, and writes Playwright tests.

**Two-field state model (stage + status):**

| Stage | Status | Meaning |
|-------|--------|---------|
| `development` | `pending` | Ready for developer agent |
| `development` | `active` | Developer is working |
| `reviewing` | `pending` | Ready for reviewer agent |
| `merging` | `pending` | Ready for integrator agent |
| `acceptance` | `pending` | Ready for tester agent |
| `backlog` | `pending` | Backlog/parked |
| any | `blocked` | Waiting for deps / agent stuck |
| `done` | `pending` | Pipeline complete |

**Stage transitions are owned by the watcher.** Agents only set status (via `takt claim`, `takt release`, `takt block`). The watcher reads the task state after the agent finishes and calls `takt advance` or `takt reject` accordingly.

**Watcher spawns agents based on stage:**

| Stage | Agent Spawned |
|-------|---------------|
| `development` | developer |
| `reviewing` | reviewer |
| `security_review` | security-reviewer |
| `merging` | integrator |
| `acceptance` | tester |

**Parallelization:**
- Total agents capped by `max_total_agents` (default 8)

---

## Stage Transition Ownership

**The watcher owns ALL stage transitions.** Agents NEVER call `takt advance` or `takt reject`.

### Agent signals (what agents set)

| Signal | Command | When |
|--------|---------|------|
| Claim | `takt claim <id>` | Starting work |
| Success | `takt release <id>` | Work complete (non-terminal) |
| Done | `takt release <id>` | Terminal (merge done, acceptance pass) |
| Rejected | `takt release <id>` + `takt comment <id> "rejected: reason"` | Failed review/test, needs rework |
| Blocked | `takt block <id>` | Can't proceed, needs conductor |

### Watcher response (what watcher does when agent finishes)

| Task state | Watcher action |
|------------|----------------|
| status=pending, no rejection | `takt advance` → next stage |
| status=pending, rejected | `takt reject` → back to development |
| status=pending, rejected (acceptance) | Block for conductor |
| terminal stage (merging/acceptance) complete | Advance to done |
| status=blocked | Parks for conductor |

---

## Agents

### @conductor
- Entry point — user talks to conductor
- **First step**: creates a feature branch and registers it: `debussy config base_branch feature/<name>`
- Creates tasks with `takt create "title" -d "description"`
- Advances tasks to development: `takt advance <id>`
- Creates all tasks first (backlog), then advances them
- Monitors progress with `debussy board`
- **Does not write code**
- **Never merges to master** — user does that manually

### @developer
- Implements features and fixes bugs
- For `frontend` tasks: starts dev server, verifies UI visually with Playwright screenshots, writes Playwright tests
- Success: `takt release <id>` (watcher advances to reviewing)
- Blocked: `takt block <id>` (watcher parks for conductor)

### @reviewer
- Reviews code quality, security, and runs tests if the task specifies test criteria
- Approve: `takt release <id>` (watcher advances to merging)
- Reject: `takt reject <id>` (watcher sends to development)

### @tester
- Batch acceptance testing (runs after all tasks in a batch are merged)
- Runs full test suite on the base branch
- Acceptance pass: `takt release <id>` (watcher advances to done)
- Acceptance fail: `takt reject <id>` (conductor triages and creates fix tasks)

### @integrator
- Merges feature branches to conductor's base branch
- Success: `takt release <id>` (task done, acceptance happens in batch)
- Conflict: `takt reject <id>` (watcher sends to development)
- **Never merges to master**

### @security-reviewer
- Dedicated security review for tasks with the `security` tag
- Runs after standard code review passes, before merge
- OWASP-aligned checklist: trust boundaries, input validation, injection, auth, secrets, crypto, error disclosure, dependencies
- Approve: `takt release <id>` (watcher advances to merging)
- Reject: `takt reject <id>` (watcher sends to development)
- Blocked: `takt block <id>` (watcher parks for conductor)
- **Does not write code**

---

## Task Workflow

### Creating Tasks

```bash
takt create "Create User model" -d "..."                                                 # → PRJ-1
takt create "Add login endpoint" -d "..."                                                # → PRJ-2
```

Use `--deps` to serialize tasks that must run in order.

### Advancing Tasks (conductor only)
```bash
takt advance <task-id>    # moves to next stage (e.g., backlog → development)
```

---

## Code Standards

### Commit Messages
```
[PRJ-N] Brief description
```

### Branch Naming
```
feature/<name>       # conductor's base branch (created first)
feature/<task-id>    # developer sub-branches (off conductor's branch)
```

### Branching Model
```
master (manual merge only by user)
  └── feature/<name>             ← conductor's branch
        ├── feature/PRJ-1  ← developer branch (merged back by integrator)
        ├── feature/PRJ-2
        └── feature/PRJ-3
```

Merging to master is NEVER done by agents — only by the user manually.

---

## Project Structure

```
src/debussy/
  cli.py              # CLI command handlers (thin dispatch layer)
  watcher.py          # Watcher run loop and agent state management
  config.py           # Configuration, constants, stage/status definitions
  transitions.py      # Stage transition logic (state machine)
  spawner.py          # Agent spawning (tmux windows and background processes)
  pipeline_checker.py # Pipeline scanning and dependency resolution
  board.py            # Kanban board rendering
  metrics.py          # Pipeline analytics and stage duration tracking
  status.py           # Status and debug display
  tmux.py             # Tmux session and window management
  worktree.py         # Git worktree lifecycle
  diagnostics.py      # Failure diagnostics for agent deaths
  preflight.py        # Pre-spawn validation checks
  prompts/            # Agent prompt templates (one file per role)
  takt/               # Built-in SQLite task tracking
    db.py             # Database connection and schema
    models.py         # Task CRUD operations
    log.py            # Log entries and workflow operations (advance, reject, claim, etc.)
    cli.py            # CLI entry point for takt command
tests/
  test_takt_db.py     # Tests for takt database layer
  test_takt_models.py # Tests for takt task model
  test_takt_log.py    # Tests for takt log and workflow operations
  test_takt_cli.py    # Tests for takt CLI
  test_takt.py        # End-to-end takt tests
  test_transitions.py # Tests for stage transition logic
  test_spawner.py     # Tests for agent spawning
.takt/                # SQLite task database (auto-created)
```

---

## Commands

```bash
debussy start              # Start system (tmux)
debussy watch              # Run watcher
debussy board              # Show kanban board
debussy config base_branch feature/<name>  # Set conductor's base branch
takt prefix [VALUE]                       # Show or set project prefix (e.g. PKL)
takt create "title" -d "description"
takt advance <id>                          # Move task to next stage
takt show <id>
takt list
takt claim <id>                            # Mark task as active
takt release <id>                          # Mark task as pending
takt block <id>                            # Mark task as blocked
takt reject <id>                           # Send task back to development
takt comment <id> "message"
takt log <id>                              # View task history
```

**Prerequisite for frontend visual testing:** `npx playwright install`
