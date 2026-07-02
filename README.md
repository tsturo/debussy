# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer. Agents are named after composers too (e.g., `developer-beethoven`, `reviewer-chopin`).*

![Architecture](docs/architecture.png)

---

## Prerequisites

- **Python 3.10+**
- **tmux** — agents run in tmux panes/windows
- **Claude Code** (`claude` CLI) — agents are Claude Code instances
- **pipx** — for isolated CLI installation
- **git** — your project must be a git repository with an `origin` remote

## Installation

```bash
brew install tmux
pipx install git+https://github.com/tsturo/debussy.git
```

To upgrade later:

```bash
debussy upgrade
```

## Quick Start

```bash
cd your-project
debussy start
```

This opens a tmux session with three panes: conductor, board, and watcher. Talk to the conductor to plan work — it creates tasks, and the watcher automatically spawns agents to execute them.

### First Run Checklist

1. Verify your project has an `origin` remote: `git remote -v`
2. Run `debussy start` — this creates `.debussy/` and `.takt/` directories (auto-added to `.gitignore`)
3. The conductor will ask what you want to build, then create tasks and a feature branch
4. The watcher picks up tasks and spawns developer/reviewer/integrator agents automatically
5. When all tasks are done, merge the feature branch to master yourself (agents never touch master)

---

## Architecture

Debussy has three layers:

1. **Conductor** - the entry point. You talk to it, it plans work and creates tasks. It never writes code.
2. **Watcher** - the orchestration engine. Polls tasks every 5 seconds, spawns Claude agents based on stage, owns all stage transitions.
3. **Agents** - specialized Claude instances (developer, reviewer, security-reviewer, integrator, tester) that do the actual work in isolated git worktrees.

### Task Tracking (takt)

Debussy includes **takt**, a built-in SQLite task tracker. No external dependencies — tasks are stored in `.takt/` as a local SQLite database.

---

## Pipelines

### Development Pipeline

Each task flows through stages. The watcher advances tasks automatically based on agent signals. Tasks with the `security` tag get an extra security review stage. After all tasks in a batch are merged, a batch acceptance task runs.

```
Per task:      backlog → development → reviewing → merging → done
Security task: backlog → development → reviewing → security_review → merging → done
Per batch:     acceptance task (deps on all tasks) → acceptance → done
```

![Pipeline](docs/pipeline.png)

## Watcher Orchestration

The watcher is the central state machine. It runs a loop every 5 seconds:

1. **Check timeouts** - kill agents running longer than `agent_timeout` (default 1 hour)
2. **Clean up finished agents** - detect completed agents and process their results
3. **Reset orphaned tasks** - if an agent disappeared but task is still `active`, reset it
4. **Resolve dependencies** - unblock tasks whose dependencies have passed merging
5. **Spawn new agents** - for tasks with `status: pending` in an actionable stage, up to `max_total_agents`

### State Model

Two-field state model (stage + status):

| Stage | Status | Meaning |
|-------|--------|---------|
| `development` | `pending` | Ready for developer agent |
| `development` | `active` | Developer is working |
| `reviewing` | `pending` | Ready for reviewer agent |
| `merging` | `pending` | Ready for integrator agent |
| `acceptance` | `pending` | Ready for tester agent |
| `backlog` | `pending` | Backlog/parked |
| any | `blocked` | Waiting for deps / needs conductor |
| `done` | `pending` | Pipeline complete |

### Stage Transition Ownership

**The watcher owns ALL stage transitions.** Agents never call `takt advance` or `takt reject`. Agents only set status to signal their result:

| Agent Signal | Command | When |
|--------------|---------|------|
| Claim | `takt claim <id>` | Starting work |
| Success | `takt release <id>` | Work complete |
| Rejected | `takt release <id>` + `takt comment <id> "rejected: reason"` | Failed review/test |
| Blocked | `takt block <id>` | Can't proceed |

The watcher reads the task state after the agent finishes and transitions accordingly:

| Task State After Agent | Watcher Action |
|------------------------|----------------|
| `pending`, no rejection | `takt advance` → next stage |
| `pending`, rejected | `takt reject` → back to development |
| `pending`, rejected (acceptance) | Block for conductor |
| terminal stage complete | Advance to done |
| `blocked` | Parks for conductor |

### Resilience

- **Rejection cooldown**: 60 seconds before retrying a rejected task
- **Max rejections**: After 5 rejections, task is blocked and needs conductor intervention
- **Empty branch detection**: If a developer doesn't commit anything, retries up to 3 times
- **Crash recovery**: If an agent crashes within 30 seconds, counts as a failure. After 3 consecutive failures, task is parked
- **Orphan recovery**: Tasks stuck as `active` with no running agent are reset to `pending`
- **Integrator queueing**: Only one integrator runs at a time to avoid merge conflicts
- **Priority sorting**: Bugs are prioritized over features

---

## Git Worktree Isolation

Each agent works in an isolated git worktree under `.debussy-worktrees/`:

| Role | Worktree Branch |
|------|-----------------|
| Developer | New branch `feature/{task_id}` from `origin/{base}` |
| Reviewer | Detached at `origin/feature/{task_id}` (read-only) |
| Security-reviewer | Detached at `origin/feature/{task_id}` (read-only) |
| Integrator | Detached at `origin/{base}` (merge target) |
| Tester | Detached at `origin/{base}` |

Worktrees symlink `.takt/` and `.debussy/` back to the main repo so all agents share the same task database and configuration.

---

## Branching Model

```
master (manual merge only by user)
  └── feature/<name>             ← conductor's base branch
        ├── feature/PRJ-1  ← developer branch (merged back by integrator)
        ├── feature/PRJ-2
        └── feature/PRJ-3
```

Agents never merge to master.

---

## Agents

| Agent | Role | Terminal? |
|-------|------|-----------|
| **conductor** | Creates tasks, monitors progress, never writes code | N/A |
| **developer** | Implements features and fixes on feature branch | No |
| **reviewer** | Reviews code quality, runs tests | No |
| **security-reviewer** | OWASP-aligned security review for tasks with `security` tag | No |
| **integrator** | Merges feature branch to conductor's base branch | Yes |
| **tester** | Batch acceptance testing after all tasks merged | Yes |

---

## Kanban Board

![Board](docs/board.png)

---

## Commands

### Debussy

```bash
debussy start [--paused] [requirement]  # Start tmux session; optional initial requirement
debussy watch                           # Run watcher only
debussy board [-p PREFIX]               # Kanban board view (optional project filter)
debussy config [key] [value]            # View or set config
debussy clear [-f]                      # Clear all tasks and worktrees
debussy pause                           # Pause pipeline, kill agents, reset active tasks
debussy resume                          # Resume paused pipeline
debussy kill [--all]                    # Kill current debussy tmux session (or --all)
debussy kill-agent <name|task-id>       # Kill a single agent
debussy sessions                        # List running debussy sessions
debussy connect [name]                  # Attach to a running session
debussy upgrade                         # Upgrade via pipx to latest
```

### Takt (task tracking)

```bash
takt prefix [VALUE]                    # Show or set project prefix (e.g. PKL)
takt create "title" -d "description"   # Create task (returns PRJ-N ID)
takt advance <id>                      # Move task to next stage
takt show <id>                         # Show task details
takt list                              # List all tasks
takt claim <id>                        # Mark task as active
takt release <id>                      # Mark task as pending
takt block <id>                        # Mark task as blocked
takt reject <id>                       # Send task back to development
takt comment <id> "message"            # Add comment to task
takt log <id>                          # View task history
takt project add <PREFIX> <NAME>       # Add a project
takt project list                      # List projects
takt project default [PREFIX]          # Show or switch default project
takt project rm <PREFIX>               # Remove a project
```

---

## Task Workflow

### Creating Tasks

```bash
takt create "Implement feature X" -d "Description of what to do"
takt advance <task-id>    # moves backlog → development
```

### Batch Acceptance

```bash
takt create "Acceptance testing" -d "Run full test suite" --deps "PRJ-1,PRJ-2"
takt advance <id>
```
The acceptance task stays blocked until all dependencies have passed merging.

---

## tmux Layout

```
┌───────────┬──────────┬─────────┐
│           │          │         │
│ conductor │  board   │ watcher │
│           │          │         │
└───────────┴──────────┴─────────┘
```

- **conductor**: Main Claude instance for task creation
- **board**: Auto-refreshing kanban board (updates every 5s)
- **watcher**: Agent spawner logs

Use `debussy connect` to reattach to a running session, or `debussy sessions` to list sessions across projects.

---

## Project Structure

```
src/debussy/
  __main__.py          # CLI entry point (subcommand parsing)
  cli.py               # CLI command handlers
  agent.py             # AgentInfo dataclass and shared agent utilities
  watcher.py           # Watcher run loop and agent lifecycle
  config.py            # Configuration, stage/status constants, defaults
  transitions.py       # Stage transition logic (state machine)
  spawner.py           # Agent spawning (tmux windows and background processes)
  pipeline_checker.py  # Pipeline scanning and dependency resolution
  preflight.py         # Pre-spawn validation checks
  board.py             # Kanban board rendering
  status.py            # Runtime info helpers (agents, branches, base)
  tmux.py              # Tmux session and window management
  worktree.py          # Git worktree lifecycle
  diagnostics.py       # Failure diagnostics for agent deaths
  hooks.py             # Claude Code hook installation
  prompts/             # Agent prompt templates (one file per role)
  takt/                # Built-in SQLite task tracking
    db.py              # Database connection and schema
    models.py          # Task CRUD operations
    log.py             # Log entries and workflow operations
    cli.py             # CLI entry point for takt command
tests/
  test_cli_sessions.py
  test_config.py
  test_diagnostics.py
  test_hooks.py
  test_integrator_prompt_content.py
  test_pipeline_checker.py
  test_preflight.py
  test_spawner.py
  test_takt.py
  test_takt_cli.py
  test_takt_db.py
  test_takt_log.py
  test_takt_models.py
  test_tmux.py
  test_transitions.py
  test_worktree.py
.takt/                 # SQLite task database (auto-created)
.debussy/              # Local state, config, logs (auto-created)
```

---

## Configuration Reference

Settings are stored in `.debussy/config.json`. Defaults:

| Key | Default | Description |
|-----|---------|-------------|
| `max_total_agents` | 8 | Max concurrent agents across all roles |
| `max_role_agents` | 10 per role | Per-role concurrency cap (developer, reviewer, security-reviewer, integrator, tester) |
| `use_tmux_windows` | false | Spawn agents as tmux windows instead of background processes |
| `agent_provider` | claude | CLI binary used to spawn agents |
| `agent_timeout` | 3600 | Kill agents after this many seconds |
| `monitor_interval` | 240 | Conductor heartbeat interval (seconds) |
| `notify_conductor` | false | Notify the conductor pane when tasks finish |
| `test_command` | — | Optional command the integrator runs during auto-resolve |
| `base_branch` | — | Conductor's feature branch (set per feature) |
| `autonomy` | auto | `auto`: conductor never asks mid-run; `manual`: asks at decision points |
| `role_models` | see below | Claude model per agent role |
| `role_efforts` | see below | Reasoning effort per agent role |

Default model and effort assignments:

| Role | Model | Effort |
|------|-------|--------|
| conductor | claude-fable-5 | high |
| developer | claude-sonnet-5 | medium |
| reviewer | claude-opus-4-8 | high |
| security-reviewer | claude-fable-5 | high |
| integrator | claude-sonnet-5 | low |
| tester | claude-sonnet-5 | low |

Override any role's model or effort:

```bash
debussy config role_models '{"developer": "claude-opus-4-8"}'
debussy config role_efforts '{"developer": "high"}'
```

### tmux Windows Mode

When `use_tmux_windows` is enabled, agents spawn as separate tmux windows instead of background processes:

- Real-time output visible (no log buffering)
- Switch between agents with `Ctrl-b n/p` or `Ctrl-b w`
- Window closes when agent finishes

---

## License

MIT
