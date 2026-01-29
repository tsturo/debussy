# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer.*

---

## Quick Start

```bash
# Install
brew install tmux beads
pipx install git+https://github.com/tsturo/debussy.git

# Run
cd your-project
bd init
debussy start
```

---

## How It Works

The **watcher** polls bead statuses every 5 seconds and spawns Claude agents:

| Status | Agent | Next Status |
|--------|-------|-------------|
| `open` | developer | `testing` |
| `testing` | tester | `reviewing` |
| `reviewing` | reviewer | `merging` |
| `merging` | integrator | `acceptance` |
| `acceptance` | tester | `done` |

```
open → testing → reviewing → merging → acceptance → done
  ↓        ↓          ↓           ↓          ↓
dev     tester    reviewer   integrator   tester
  ↑        │          │
  └────────┴──────────┘  (on failure, status → open)
```

**Parallel:** Multiple developers/testers/reviewers work simultaneously.
**Singleton:** Only one integrator (avoids merge conflicts).
**Blocked beads:** Skipped automatically.

---

## Agents

| Agent | Does |
|-------|------|
| **conductor** | Creates tasks. Never writes code. |
| **developer** | Implements on feature branch, sets status → `testing` |
| **tester** | Tests code, sets status → `reviewing` (or `open` on fail) |
| **reviewer** | Reviews code, sets status → `merging` (or `open` for changes) |
| **integrator** | Merges to develop, sets status → `acceptance` |

---

## Commands

```bash
debussy start     # Start tmux session (conductor + watcher + status)
debussy watch     # Run watcher only
debussy status    # Show pipeline status
```

---

## Creating Tasks

Conductor creates beads:
```bash
bd create "Implement feature X"   # Creates with status=open
```

Or manually:
```bash
bd create "Fix bug Y" --status open
```

Watcher detects `open` status → spawns developer → pipeline begins.

---

## Setup for Existing Project

```bash
cd your-project
bd init

# Copy agent configs
git clone https://github.com/tsturo/debussy.git /tmp/debussy
cp -r /tmp/debussy/.claude/subagents .claude/
cp /tmp/debussy/CLAUDE.md .

debussy start
```

---

## License

MIT
