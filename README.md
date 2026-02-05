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

The **watcher** polls bead statuses every 5 seconds and spawns Claude agents:

| Status | Agent | Next Status |
|--------|-------|-------------|
| `open` | developer | `reviewing` |
| `reviewing` | reviewer | `testing` |
| `testing` | tester | `merging` |
| `merging` | integrator | `acceptance` |
| `acceptance` | tester | `done` |

```
planning → open → reviewing → testing → merging → acceptance → done
             ↓         ↓          ↓          ↓           ↓
          developer  reviewer   tester   integrator    tester
             ↑         │          │
             └─────────┴──────────┘  (on failure → open, on blocker → planning)
```

**Parallel:** Up to 3 developers/testers/reviewers work simultaneously (configurable).
**Singleton:** Only one integrator (avoids merge conflicts).
**Dynamic limits:** Total agents capped at 6; reduces per-role limits when busy.
**Blocked beads:** Skipped automatically.

---

## Agents

Agents are named after composers (e.g., `developer-beethoven`, `tester-chopin`).

| Agent | Does |
|-------|------|
| **conductor** | Creates tasks. Never writes code. |
| **developer** | Implements on feature branch, sets status → `reviewing` |
| **reviewer** | Reviews code, sets status → `testing` (or `open` for changes) |
| **tester** | Tests code, writes automated tests, sets status → `merging` (or `open` on fail) |
| **integrator** | Merges to develop, deletes feature branch, sets status → `acceptance` |

### Agent Communication

If blocked or requirements unclear, agents:
1. Add comment: `bd comment <id> "Question: ..."`
2. Return to planning: `bd update <id> --status planning`
3. Conductor sees it in status view and can clarify

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
dbs debug                # Troubleshoot pipeline detection
```

---

## Configuration

```bash
dbs config                          # Show all
dbs config max_developers 5         # Set max developers
dbs config max_testers 3            # Set max testers
dbs config max_reviewers 3          # Set max reviewers
dbs config max_total_agents 8       # Set total agent limit
dbs config use_tmux_windows true    # Spawn agents as tmux windows
```

Defaults: 3 per role, 6 total, tmux windows off.

### tmux Windows Mode

When `use_tmux_windows` is enabled, agents spawn as separate tmux windows instead of background processes:

- Real-time output visible (no log buffering)
- Switch between agents with `Ctrl-b n/p` or `Ctrl-b w`
- Window closes when agent finishes (press Enter to dismiss)
- Works only when watcher runs inside tmux session

---

## Creating Tasks

Conductor creates beads in planning status, then releases:
```bash
bd create "Implement feature X" --status planning
bd update bd-001 --status open  # Release to developer
```

Or directly:
```bash
bd create "Fix bug Y" --status open
```

Watcher detects `open` status → spawns developer → pipeline begins.

---

## tmux Layout

```
┌──────────┬──────────┬──────────┐
│conductor │          │ watcher  │
├──────────┤  status  ├──────────┤
│   cmd    │          │   git    │
└──────────┴──────────┴──────────┘
```

- **conductor**: Main Claude instance for task creation
- **cmd**: Shell for manual commands
- **status**: Auto-refreshing pipeline view
- **watcher**: Agent spawner logs
- **git**: Branch/commit visualization

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
