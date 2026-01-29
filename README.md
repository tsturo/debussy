# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer.*

---

## Prerequisites

- **Python 3.10+**
- **tmux**
- **beads** (`bd` CLI)

```bash
brew install tmux beads
brew install pipx && pipx ensurepath
```

---

## Quick Start

```bash
pipx install git+https://github.com/tsturo/debussy.git
cd your-project
debussy start
```

Opens tmux with split panes:
```
┌──────────┬──────────┐
│          │ watcher  │
│conductor ├──────────┤
│          │ status   │
└──────────┴──────────┘
```

---

## How It Works

### Pipeline

Tasks flow through statuses automatically:

```
pending → testing → reviewing → merging → acceptance → done
   ↓         ↓          ↓           ↓          ↓
developer  tester   reviewer   integrator   tester
```

The **watcher** polls bead statuses and spawns agents:

| Status | Agent |
|--------|-------|
| `pending` | developer |
| `testing` | tester |
| `reviewing` | reviewer |
| `merging` | integrator |
| `acceptance` | tester |

**Parallelization:** Multiple developers/testers/reviewers run simultaneously. Integrator is singleton.

**Feedback loops:** Failed tests or review → status back to `pending` → developer picks it up again.

### Agents

| Agent | Role |
|-------|------|
| **conductor** | Creates tasks, monitors progress. Never writes code. |
| **developer** | Implements features on feature branches. |
| **tester** | Runs tests, writes automated tests. |
| **reviewer** | Reviews code for quality and security. |
| **integrator** | Merges to develop branch. |

---

## Usage

Talk to conductor:

```
I need user authentication with JWT.
```

Conductor creates tasks:
```bash
bd create "Implement JWT auth" --status pending
bd create "Add login endpoint" --status pending
```

Watcher automatically spawns agents as tasks move through the pipeline.

---

## Commands

```bash
debussy start              # Start tmux session
debussy status             # Show pipeline status
debussy watch              # Run watcher only
debussy upgrade            # Upgrade to latest
```

---

## Setup for New Project

```bash
cd your-project
bd init

# Copy agent configs
git clone https://github.com/tsturo/debussy.git /tmp/debussy
mkdir -p .claude/subagents
cp /tmp/debussy/.claude/subagents/*.md .claude/subagents/
cp /tmp/debussy/CLAUDE.md .

debussy start
```

---

## License

MIT
