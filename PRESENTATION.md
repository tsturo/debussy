# Debussy — Multi-Agent Orchestration for Claude Code

*Named after Claude Debussy, the impressionist composer.*

---

## What Is Debussy?

Debussy is an orchestration layer that turns Claude Code into a team of specialized AI agents. Instead of one Claude instance doing everything, Debussy splits work across multiple agents — each responsible for a single phase of the development lifecycle.

You talk to the **conductor**. The conductor creates tasks. A **watcher** process detects new tasks and automatically spawns the right agent. When an agent finishes, the next one picks up where it left off.

The result: parallel development with built-in code review, testing, and integration — all automated.

---

## Core Concepts

### 1. Status-Driven Pipeline

The entire system is driven by **task status changes**. There are no explicit messages between agents. Instead:

- Each task (called a "bead") has a status
- The watcher polls statuses every 5 seconds
- When a status matches an agent role, the watcher spawns that agent
- When the agent finishes, it changes the status — triggering the next agent

This is the key insight: **status is the only communication channel**.

### 2. Stateless Agents

Agents are ephemeral. They spawn, do their job, update the status, and exit. All persistent state lives in:

- **Beads** — task database (title, description, status, comments)
- **Git** — the code itself
- **Config** — `.debussy/config.json`

If an agent crashes, the watcher can simply spawn a new one — the bead still has all the context.

### 3. Separation of Concerns

Each agent has a single responsibility and limited permissions:

| Agent | Writes Code | Reviews Code | Merges | Creates Tasks |
|-------|:-----------:|:------------:|:------:|:-------------:|
| conductor | | | | yes |
| developer | yes | | | |
| reviewer | | yes | | |
| tester | yes (tests) | | | |
| integrator | | | yes | |
| investigator | | yes | | |

The conductor never writes code. The developer never merges. The reviewer never edits files. This separation prevents mistakes and enforces quality gates.

---

## The Two Pipelines

### Development Pipeline

For building features and fixing bugs:

```
planning → development → reviewing → testing → merging → acceptance → done
               ↓             ↓          ↓          ↓           ↓
           developer      reviewer    tester   integrator    tester
```

| Phase | Agent | What Happens | On Failure |
|-------|-------|-------------|------------|
| planning | none | Conductor plans the task | — |
| development | developer | Creates branch, implements, commits, pushes | → open |
| reviewing | reviewer | Reviews diff against base branch | → open + comment |
| testing | tester | Writes tests, runs test suite | → open + comment |
| merging | integrator | Merges feature branch into base branch | → open + comment |
| acceptance | tester | Tests on merged base branch | → open + comment |
| done | none | Task complete | — |

On failure at any stage, the task goes back to `open` with a comment explaining what went wrong. The conductor can then re-release it.

### Investigation Pipeline

For research tasks that need parallel exploration:

```
planning → investigating (parallel) → consolidating → done
                  ↓                         ↓
            investigator              investigator
```

Multiple investigators work in parallel on different areas. A consolidation bead (blocked by all investigation beads) waits for them to finish, then synthesizes findings into a `.md` file. The conductor reads this file and creates development tasks.

---

## Branching Model

```
master                              ← user merges manually
  └── feature/user-auth             ← conductor's base branch
        ├── feature/bd-001          ← developer branch
        ├── feature/bd-002          ← developer branch
        └── feature/bd-003          ← developer branch
```

- The conductor creates a **base branch** off master (e.g., `feature/user-auth`)
- Each developer creates a **sub-branch** off the base branch (e.g., `feature/bd-001`)
- The integrator merges sub-branches back into the base branch
- Merging the base branch to master is **always done manually by the user**

This keeps master safe from automated changes.

---

## Agent Lifecycle

### How Agents Spawn

```
Watcher polls (every 5s)
    ↓
bd list --status development
    ↓
Found bd-001 in "development" status
    ↓
Not already running? Not blocked? Capacity available?
    ↓
Spawn: developer-beethoven for bd-001
    ↓
Agent gets prompt with bead ID and base branch context
```

### How Agents Finish

```
Developer finishes implementation
    ↓
bd update bd-001 --status reviewing
    ↓
Watcher detects status changed (no longer "development")
    ↓
Marks developer-beethoven as done, cleans up
    ↓
Next poll: bd-001 now in "reviewing" → spawns reviewer
```

### Naming

Each agent gets a random composer name: `developer-beethoven`, `tester-chopin`, `reviewer-debussy`. This makes it easy to identify agents in tmux windows and logs.

---

## Safety Mechanisms

### Pre-Tool Hooks

Before any `bd` command executes, a validation hook checks:

- **Create validation**: Tasks must be created as `planning` — you can't create a task directly in `development` or `testing`
- **Status transition validation**: Each role can only set specific statuses
  - Developer → `reviewing` or `open`
  - Reviewer → `testing` or `open`
  - Tester → `merging`, `done`, or `open`
  - Integrator → `acceptance` or `open`
  - Investigator → `done` or `open`

### Stop Hooks

When an agent tries to exit, a hook verifies the bead is no longer in an agent-owned status. If a developer tries to exit while the bead is still in `development`, the exit is blocked.

### Crash Loop Protection

If an agent crashes within 30 seconds of spawning, the watcher increments a failure counter. After 3 retries, the bead is parked — no more agents spawned for it until manually reset.

### Agent Timeout

Agents running longer than 15 minutes are killed. The bead gets a comment explaining the timeout and is reset to `planning`.

---

## Parallelization

- Up to **6 agents** run simultaneously (configurable)
- Multiple developers, testers, and reviewers can work in parallel
- The integrator is **serialized** — only one runs at a time to avoid merge conflicts
- Blocked beads (waiting on dependencies) are automatically skipped

```
Example: 3 development tasks released simultaneously

developer-bach     → bd-001 (User model)
developer-mozart   → bd-002 (Login endpoint)
developer-schubert → bd-003 (Login form)

All three work in parallel, each on their own branch.
```

---

## tmux Interface

When you run `debussy start`, you get a 4-pane tmux session:

```
┌──────────┬──────────┬─────────┐
│conductor │          │         │
├──────────┤  status  │ watcher │
│   cmd    │          │         │
└──────────┴──────────┴─────────┘
```

| Pane | Purpose |
|------|---------|
| **conductor** | Claude instance you interact with directly |
| **cmd** | Shell for manual commands (`bd list`, `git log`, etc.) |
| **status** | Auto-refreshing pipeline view (updates every 5s) |
| **watcher** | Agent spawner logs — see what's being spawned and finished |

Each spawned agent gets its own **tmux window**. Switch between them with `Ctrl-b w` to watch agents work in real-time.

---

## Walkthrough: Feature Request to Completion

**User**: "Add user authentication with JWT"

### Step 1 — Conductor Plans

The conductor (talking to you) creates the feature branch and tasks:

```bash
git checkout -b feature/user-auth && git push -u
debussy config base_branch feature/user-auth

bd create "Create User model" -d "..." --status planning       # → bd-001
bd create "Add login endpoint" -d "..." --status planning       # → bd-002
bd create "Add auth middleware" -d "..." --status planning       # → bd-003
```

### Step 2 — Conductor Releases

```bash
bd update bd-001 --status development
bd update bd-002 --status development
bd update bd-003 --status development
```

### Step 3 — Agents Take Over

The watcher spawns 3 developers in parallel. From here, the pipeline is fully automated:

```
bd-001: development → reviewing → testing → merging → acceptance → done
bd-002: development → reviewing → testing → merging → acceptance → done
bd-003: development → reviewing → testing → merging → acceptance → done
```

Each task goes through 5 agent handoffs automatically. If any agent finds an issue, the task returns to `open` with a comment, and the conductor can re-release it.

### Step 4 — User Merges to Master

When all tasks are `done`, the base branch has the complete feature. The user reviews and merges to master manually.

---

## Commands Reference

| Command | What It Does |
|---------|-------------|
| `dbs start [requirement]` | Create tmux session, launch conductor |
| `dbs status` | Show pipeline: active tasks, backlog, done |
| `dbs watch` | Run watcher (agent spawner) |
| `dbs pause` | Stop everything, reset beads to planning |
| `dbs restart [-u]` | Pause and restart (optionally upgrade first) |
| `dbs config [key] [value]` | View or set configuration |
| `dbs init` | Initialize beads with pipeline statuses |
| `dbs clear [-f]` | Wipe all tasks (backs up first) |
| `dbs backup` | Backup beads database |
| `dbs upgrade` | Upgrade to latest version |
| `dbs debug` | Troubleshoot pipeline detection |

---

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `max_total_agents` | 6 | Maximum concurrent agents |
| `use_tmux_windows` | true | Spawn agents as tmux windows (vs background) |
| `base_branch` | — | Conductor's feature branch (set per project) |

---

## Project Structure

```
src/debussy/
  watcher.py        # Polls beads, spawns agents, manages lifecycle
  cli.py            # All CLI commands (start, status, pause, etc.)
  config.py         # Configuration, constants, status-to-role mapping
  prompts.py        # Agent prompts (conductor, developer, reviewer, etc.)
  __main__.py       # CLI argument parser and entry point

.claude/
  subagents/        # Agent role definitions (markdown files)
  hooks/            # Safety hooks (pre-tool validation, stop checks)
  settings.json     # Hook configuration

.debussy/
  config.json       # Runtime configuration
  watcher_state.json # Currently running agents
  logs/             # Agent output logs (background mode)
  investigations/   # Consolidation findings (.md files)
  backups/          # Beads database backups
```

---

## Key Takeaways

1. **Status is the API** — agents communicate only through bead status changes
2. **Agents are disposable** — crash? spawn a new one, the bead has all context
3. **Quality gates are enforced** — every change goes through review, testing, and integration
4. **Parallelism is automatic** — release multiple tasks, agents work simultaneously
5. **Master is protected** — agents never touch master, only the user merges manually
6. **Safety hooks prevent mistakes** — agents can only set statuses their role allows
