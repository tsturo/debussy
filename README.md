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
bd init
dbs start
```

---

## How It Works

The **watcher** polls beads every 5 seconds and spawns Claude agents based on **stage labels**.

The **conductor** (you talk to it directly) creates tasks, then releases them by adding a stage label. The watcher spawns agents for beads with `status: open` and a `stage:*` label — beads without a stage label are backlog.

### Status Model

| bd status | Meaning |
|-----------|---------|
| `open` + stage label | Ready for agent |
| `open` (no stage label) | Backlog/parked |
| `in_progress` | Agent is working |
| `closed` | Pipeline complete |
| `blocked` | Waiting for deps |

### Development Pipeline

| Stage Label | Agent | Next Stage |
|-------------|-------|------------|
| `stage:development` | developer | `stage:reviewing` |
| `stage:reviewing` | reviewer | `stage:testing` |
| `stage:testing` | tester | `stage:merging` |
| `stage:merging` | integrator | `stage:acceptance` |
| `stage:acceptance` | tester | `closed` |

```
open → stage:development → stage:reviewing → stage:testing → stage:merging → stage:acceptance → closed
              ↓                  ↓                ↓               ↓                ↓
          developer           reviewer          tester        integrator         tester
              ↑                  │                │               │
              └──────────────────┴────────────────┴───────────────┘  (on failure → stage:development)
```

### Investigation Pipeline

| Stage Label | Agent | Result |
|-------------|-------|--------|
| `stage:investigating` | investigator | `closed` |
| `stage:consolidating` | investigator | `closed` |

```
stage:investigating (parallel) → stage:consolidating → .md file → conductor creates dev tasks
          ↓                              ↓
     investigator                   investigator
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
| **developer** | Implements on feature branch |
| **reviewer** | Reviews code for quality and security |
| **tester** | Tests code, runs acceptance tests |
| **integrator** | Merges feature branches to conductor's base branch |

### Agent Workflow

**The watcher owns all stage transitions.** Agents only set status:

1. Watcher finds bead with `status: open` + stage label → spawns agent
2. Agent claims: `bd update <id> --status in_progress`
3. Agent works
4. Agent signals result:
   - Success: `bd update <id> --status open`
   - Rejection: `bd update <id> --status open --add-label rejected`
   - Terminal: `bd update <id> --status closed`
   - Blocked: `bd update <id> --status blocked`
5. Watcher detects completion → moves stage label automatically

---

## Commands

```bash
dbs start [requirement]  # Start tmux session
dbs watch                # Run watcher only
dbs status               # Show pipeline status
dbs config [key] [value] # View/set config
dbs backup               # Backup beads database
dbs clear [-f]           # Clear all beads (with backup)
dbs upgrade              # Upgrade to latest version
dbs restart [-u]         # Restart session (-u to upgrade first)
dbs pause                # Stop watcher, kill agents, reset beads to open
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
bd create "Implement feature X" -d "Description of what to do"
bd update <bead-id> --add-label stage:development
```
Conductor creates tasks (backlog), then releases them with `--add-label`. Watcher detects `stage:development` label → spawns developer → pipeline begins.

### Parallel Investigation
```bash
bd create "Investigate area A" -d "Research details"
bd create "Investigate area B" -d "Research details"
bd create "Consolidate findings" -d "Synthesize results" --deps "bd-001,bd-002"
bd update bd-001 --add-label stage:investigating
bd update bd-002 --add-label stage:investigating
bd update bd-003 --add-label stage:consolidating
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
bd init

# Optional: Copy agent configs
git clone https://github.com/tsturo/debussy.git /tmp/debussy
cp -r /tmp/debussy/.claude/subagents .claude/
cp /tmp/debussy/CLAUDE.md .

dbs start
```

---

## License

MIT
