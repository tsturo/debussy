# Takt — Design Spec

## Overview

Takt is a SQLite-based task management system purpose-built for debussy. It replaces the external `bd` (beads) tool, eliminating the Dolt SQL server that causes instability under parallel agent load.

## Problem

Beads uses Dolt (a versioned SQL database) as its backend. Dolt runs as a local SQL server process. Under parallel load (8 agents calling `bd` concurrently), the server becomes unreachable, spawns duplicate instances on random ports, loses PID tracking files, and cascades into data loss. This is machine-specific and not reliably fixable through configuration.

Debussy uses none of Dolt's versioning features (history, branching, diffing). It needs CRUD on tasks with stages, statuses, dependencies, and comments.

## Design Decisions

### SQLite over Dolt/JSONL
- **Decided:** SQLite with WAL mode, no server process
- **Why:** File-based (no networking, no ports, no server lifecycle), WAL mode handles concurrent readers + single writer, crash-safe natively
- **Rejected:** Dolt (server instability under load), JSONL no-db mode (untested concurrency, still depends on external tool)

### Two-field state model over labels
- **Decided:** Explicit `stage` and `status` columns replace the label-based stage tracking
- **Why:** Current model uses `status=open + label=stage:reviewing` which requires parsing labels and juggling add/remove operations. Two columns are directly queryable and eliminate transition complexity
- **Rejected:** Single unified status field (combinatorial explosion: `development_pending`, `development_active`, etc.)

### Unified log table over separate comments + events
- **Decided:** Single `log` table for comments, state transitions, and assignments
- **Why:** Replaces three separate mechanisms (bd comments, pipeline_events.jsonl, watcher logs). Metrics derived from log queries, not denormalized columns. Single source of truth.
- **Rejected:** Separate comments table (redundant with transition log), cached metrics columns (two sources of truth)

### Python API + thin CLI over CLI-only
- **Decided:** Core logic as Python module, CLI as thin wrapper
- **Why:** Debussy internals (watcher, transitions, pipeline_checker) get direct function calls — no subprocess overhead, no timeouts, no JSON parsing. Agents still need a CLI for shell sessions.
- **Rejected:** CLI-only (subprocess overhead for every operation), Python-only (agents need shell commands)

### Dependencies in takt, resolution in debussy
- **Decided:** Takt stores dependency links. Debussy decides when to release tasks.
- **Why:** Dependencies are simple relational data (join table + query). Release logic is orchestration policy that may evolve — belongs in debussy, not the storage layer.

### Tags as JSON array over separate table
- **Decided:** `tags TEXT DEFAULT '[]'` on the task row
- **Why:** Only 3-4 tags exist (security, frontend, priority). JSON array with `json_each()` is simple and sufficient. Separate table is overkill.

## Data Model

```sql
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    stage           TEXT DEFAULT 'backlog'
                    CHECK(stage IN ('backlog','development','reviewing',
                                    'security_review','merging','acceptance','done')),
    status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','active','blocked')),
    tags            TEXT DEFAULT '[]',
    rejection_count INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE dependencies (
    task_id       TEXT REFERENCES tasks(id),
    depends_on_id TEXT REFERENCES tasks(id),
    PRIMARY KEY (task_id, depends_on_id)
);

CREATE TABLE log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT REFERENCES tasks(id),
    timestamp TEXT DEFAULT (datetime('now')),
    type      TEXT CHECK(type IN ('comment','transition','assignment')),
    author    TEXT,
    message   TEXT
);

CREATE INDEX idx_tasks_stage_status ON tasks(stage, status);
CREATE INDEX idx_log_task_id ON log(task_id);
CREATE INDEX idx_deps_task ON dependencies(task_id);
CREATE INDEX idx_deps_dep ON dependencies(depends_on_id);
```

## Stage/Status Model

### Stages (pipeline position)
| Stage | Meaning |
|-------|---------|
| `backlog` | Created, not yet released |
| `development` | Ready for / being developed |
| `reviewing` | Ready for / being reviewed |
| `security_review` | Security review (tasks with `security` tag) |
| `merging` | Ready for / being merged |
| `acceptance` | Batch acceptance testing |
| `done` | Complete |

### Statuses (work state within a stage)
| Status | Meaning |
|--------|---------|
| `pending` | Ready for an agent to pick up |
| `active` | Agent is working on it |
| `blocked` | Needs conductor intervention |

### Transition rules
- Watcher finds tasks: `stage=X AND status=pending` → spawns agent
- Agent claims: `status → active`
- Agent succeeds: `status → pending` (watcher advances stage)
- Agent rejects: rejection flow (see below)
- Agent blocked: `status → blocked` (watcher parks for conductor)

### Rejection flow
1. Agent sets `status=pending` + signals rejection
2. Watcher increments `rejection_count`, moves `stage → development, status → pending`
3. If `rejection_count >= 3` → `status=blocked` instead (conductor triages)

### Stage progression
```
backlog → development → reviewing → [security_review] → merging → done
                                                              ↗
                                    acceptance → done
```
Security review only for tasks tagged `security`. Acceptance is batch-level (separate task with deps on all phase tasks).

## Architecture

```
src/debussy/takt/
    __init__.py       # Public API: create_task, get_task, list_tasks, update_task,
                      #             advance_task, reject_task, claim_task, release_task,
                      #             block_task, add_comment, get_log, get_deps, init_db
    db.py             # SQLite connection management, WAL setup, migrations, busy timeout
    models.py         # Task CRUD, dependency operations, query functions
    log.py            # Log entries, auto-logging transitions, metrics queries
    cli.py            # argparse CLI entry point → calls public API functions
```

### Python API (debussy internals)

```python
# Task lifecycle
create_task(title, description='', tags=None, deps=None) -> Task
get_task(task_id) -> Task | None
list_tasks(stage=None, status=None, tag=None) -> list[Task]
update_task(task_id, **fields) -> Task

# Workflow operations (auto-log transitions)
advance_task(task_id, to_stage=None) -> Task     # next stage
reject_task(task_id) -> Task                      # back to dev, increment counter
claim_task(task_id, agent) -> Task                # status → active
release_task(task_id) -> Task                     # status → pending
block_task(task_id) -> Task                       # status → blocked

# Comments & log
add_comment(task_id, author, message) -> None
get_log(task_id, type=None) -> list[LogEntry]

# Dependencies
get_unresolved_deps(task_id) -> list[str]

# Setup
init_db(project_dir) -> None
```

### CLI (agent-facing)

```
takt create "title" -d "description" [--deps id1,id2] [--tags security,frontend]
takt show <id> [--json]
takt list [--stage X] [--status Y] [--json]
takt advance <id> [--to stage]
takt reject <id>
takt claim <id> --agent <name>
takt release <id>
takt block <id>
takt comment <id> "message" [--author name]
takt log <id> [--type transition|comment|assignment]
takt init
```

## Concurrency Model

- SQLite WAL mode: multiple concurrent readers, single writer with automatic queuing
- Busy timeout: 5 seconds (writes take microseconds, contention effectively zero)
- No server process, no ports, no networking
- Connection-per-call (no long-lived connections)
- Database file: `.takt/takt.db` in project root

## Migration Path

### Phase 1: Build takt module
New files only. No existing debussy code touched.
- `src/debussy/takt/` — full module with db, models, log, cli
- Tests for CRUD, transitions, concurrency, CLI
- Entry point registration in setup/pyproject

### Phase 2: Rewire debussy internals
- Replace `bead_client.py` subprocess calls with takt Python API
- Simplify `transitions.py` — `advance_task()` and `reject_task()` replace label juggling
- Simplify `pipeline_checker.py` — SQL queries replace bd list + filtering
- Remove `_ensure_dolt_server()` from watcher
- Remove `pipeline_events.jsonl` dependency from metrics

### Phase 3: Update agent prompts
- Rewrite 6 prompts: bd commands → takt commands
- Prompts get simpler (no label manipulation instructions)

### Phase 4: Cleanup
- Remove `bead_client.py`
- Remove dolt/bd references
- Update CLAUDE.md
- Update docs

No data migration needed — conductor recreates tasks each session.

## What This Eliminates

- Dolt SQL server process and lifecycle management
- Port binding, PID files, lock files
- Circuit breaker / auto-start / auto-stop behavior
- `pipeline_events.jsonl` (replaced by log table)
- Label-based stage tracking (replaced by stage column)
- `_ensure_dolt_server()` in watcher
- All subprocess calls for task operations in debussy internals
