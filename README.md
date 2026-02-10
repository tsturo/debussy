# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer. Agents are named after composers too.*

---

## Quick Start

```bash
# Install
brew install tmux beads
pipx install git+https://github.com/tsturo/debussy.git

# Run
cd your-project
dbs init
dbs start
```

---

## How It Works

The **watcher** polls bead statuses every 5 seconds and spawns Claude agents.

The **conductor** (you talk to it directly) creates tasks as `planning`, then releases them by changing the status. The watcher only spawns agents for specific statuses — `planning` and `open` are ignored.

### Development Pipeline

| Status | Agent | Next Status |
|--------|-------|-------------|
| `development` | developer | `reviewing` |
| `reviewing` | reviewer | `testing` |
| `testing` | tester | `merging` |
| `merging` | integrator | `acceptance` |
| `acceptance` | tester | `done` |

```
planning → development → reviewing → testing → merging → acceptance → done
               ↓             ↓          ↓          ↓           ↓
           developer      reviewer    tester   integrator    tester
               ↑             │          │          │
               └─────────────┴──────────┴──────────┘  (on failure → open with comment)
```

### Investigation Pipeline

| Status | Agent | Next Status |
|--------|-------|-------------|
| `investigating` | investigator | `done` |
| `consolidating` | investigator | `done` |

```
investigating (parallel) → consolidating → .md file → conductor creates dev tasks
       ↓                         ↓
  investigator              investigator
```

Investigators research in parallel and document findings as comments. A consolidation bead (blocked by investigation beads) waits for all to finish, then the investigator synthesizes findings into an `.md` file.

**Total agents** capped at 6 (configurable).
**Blocked beads** skipped automatically.

---

## Agents

Agents are named after composers (e.g., `developer-beethoven`, `tester-chopin`).

| Agent | Does |
|-------|------|
| **conductor** | Creates tasks. Never writes code. |
| **investigator** | Researches codebase, documents findings. Also handles consolidation. |
| **developer** | Implements on feature branch, sets status → `reviewing` |
| **reviewer** | Reviews code, sets status → `testing` (or `open` for changes) |
| **tester** | Tests code, sets status → `merging` (or `open` on fail) |
| **integrator** | Merges feature branches to conductor's base branch |

### Agent Communication

If blocked or issues found, agents:
1. Add comment: `bd comment <id> "Blocked: [reason]"`
2. Return to open: `bd update <id> --status open`
3. Conductor re-releases the task when ready

---

## Commands

```bash
dbs start [requirement]  # Start tmux session
dbs watch                # Run watcher only
dbs status               # Show pipeline status (with comments, running agents)
dbs config [key] [value] # View/set config
dbs init                 # Initialize beads with pipeline statuses
dbs backup               # Backup beads database
dbs clear [-f]           # Clear all beads (with backup)
dbs upgrade              # Upgrade to latest version
dbs restart [-u]         # Restart session (-u to upgrade first)
dbs pause                # Stop watcher, kill agents, reset beads to planning
dbs debug                # Troubleshoot pipeline detection
```

---

## Configuration

```bash
dbs config                          # Show all
dbs config max_total_agents 8       # Set total agent limit
dbs config use_tmux_windows true    # Spawn agents as tmux windows
dbs config base_branch feature/foo  # Set conductor's base branch
```

Defaults: 6 total agents, tmux windows on.

### tmux Windows Mode

When `use_tmux_windows` is enabled, agents spawn as separate tmux windows instead of background processes:

- Real-time output visible (no log buffering)
- Switch between agents with `Ctrl-b n/p` or `Ctrl-b w`
- Window closes when agent finishes (press Enter to dismiss)
- Works only when watcher runs inside tmux session

---

## Creating Tasks

### Development Tasks
```bash
bd create "Implement feature X" --status planning
bd update <bead-id> --status development
```
Conductor creates tasks as `planning`, then releases them with `bd update`. Watcher detects `development` status → spawns developer → pipeline begins.

### Parallel Investigation
```bash
bd create "Investigate area A" --status planning
bd create "Investigate area B" --status planning
bd create "Consolidate findings" --deps "bd-001,bd-002" --status planning
bd update bd-001 --status investigating
bd update bd-002 --status investigating
bd update bd-003 --status consolidating
```
Investigators work in parallel. Consolidation bead stays blocked until all finish, then investigator synthesizes findings.

---

## Branching Model

```
master (manual merge only by user)
  └── feature/<name>          ← conductor's base branch
        ├── feature/bd-001    ← developer branch (merged back by integrator)
        ├── feature/bd-002
        └── feature/bd-003
```

Agents never merge to master — only the user does that manually.

---

## tmux Layout

```
┌──────────┬──────────┬─────────┐
│conductor │          │         │
├──────────┤  status  │ watcher │
│   cmd    │          │         │
└──────────┴──────────┴─────────┘
```

- **conductor**: Main Claude instance for task creation
- **cmd**: Shell for manual commands
- **status**: Auto-refreshing pipeline view (full height)
- **watcher**: Agent spawner logs (full height)

---

## Setup for Existing Project

```bash
cd your-project
dbs init

# Optional: Copy agent configs
git clone https://github.com/tsturo/debussy.git /tmp/debussy
cp -r /tmp/debussy/.claude/subagents .claude/
cp /tmp/debussy/CLAUDE.md .

dbs start
```

---

## License

MIT
