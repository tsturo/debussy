# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer.*

---

## Prerequisites

- **Python 3.10+**
- **tmux** - terminal multiplexer for split-pane layout
- **beads** - task tracking system

```bash
# macOS
brew install tmux beads
brew install pipx && pipx ensurepath
```

---

## Quick Start

```bash
# Install Debussy
pipx install git+https://github.com/tsturo/debussy.git

# Start in your project
cd your-project
debussy start
```

This opens tmux with split panes:
```
┌──────────┬──────────┐
│          │ watcher  │
│conductor ├──────────┤
│          │ status   │
└──────────┴──────────┘
```

---

## Core Concepts

### Agents

Debussy runs multiple Claude Code instances, each with a specialized role. Agents are spawned on-demand by the watcher and exit when their task is complete.

| Agent | Role | Writes Code |
|-------|------|-------------|
| **conductor** | Orchestrates all work. Receives requirements from user, delegates planning to architect, assigns tasks to developers. Never writes code. | ❌ |
| **architect** | Analyzes requirements, plans technical approach, breaks work into task beads with dependencies. Creates ADRs for architectural decisions. | ❌ |
| **developer/developer2** | Implements features on feature branches. Two developers enable parallel work and load balancing. | ✅ |
| **tester** | Does manual testing AND writes automated tests. Runs test suites, reports coverage. Also handles acceptance testing after merge. | ✅ |
| **reviewer** | Reviews code for quality, security, performance. Files issues for problems found, doesn't fix them directly. | ❌ |
| **integrator** | Merges feature branches to develop. Resolves merge conflicts. Only escalates complex conflicts to developer. | ✅ |

### Beads

Persistent task tracking using the `bd` CLI. Unlike in-memory task lists, beads survive across agent sessions.

Each bead has:
- **ID** - Unique identifier (e.g., `bd-001`)
- **Status** - Current pipeline stage
- **Assignment** - Which agent owns it
- **Dependencies** - What blocks it or what it blocks

```bash
bd create "Implement auth"    # Create task
bd list --status pending      # List by status
bd show bd-001                # View details
bd update bd-001 --status testing --assign tester
```

### Mailbox

File-based message queue for agent-to-agent communication. Each agent has an inbox directory where JSON messages are deposited.

```
.mailbox/
├── conductor/inbox/    # Receives notifications from all agents
├── architect/inbox/    # Receives planning requests
├── developer/inbox/    # Receives assignments and bug reports
├── tester/inbox/       # Receives test requests
├── reviewer/inbox/     # Receives review requests
└── integrator/inbox/   # Receives merge requests
```

When an agent completes work, it notifies conductor. When issues are found, agents notify the responsible developer.

### Watcher

The watcher is a background daemon that makes the system autonomous. It continuously monitors two things:

**1. Mailboxes** - When messages arrive in an agent's inbox, watcher spawns that agent to process them.

**2. Task statuses** - When beads reach certain statuses, watcher auto-spawns the appropriate pipeline agent:

| Status | Agent Spawned |
|--------|---------------|
| `testing` | tester |
| `reviewing` | reviewer |
| `merging` | integrator |
| `acceptance` | tester |

The watcher polls every 5 seconds and logs activity. If it seems stuck, use `debussy trigger` to manually check the pipeline.

### Pipeline

Tasks flow through automated stages. Each stage is handled by a specialist agent:

```
pending → in-progress → testing → reviewing → merging → acceptance → done
```

**Flow:**
1. **pending** - Task created, waiting for assignment
2. **in-progress** - Developer implementing on feature branch
3. **testing** - Tester runs manual + automated tests
4. **reviewing** - Reviewer checks code quality
5. **merging** - Integrator merges to develop branch
6. **acceptance** - Tester does final verification after merge
7. **done** - Complete

**Feedback loops:** If tester/reviewer/integrator find issues, they send the task back to developer and notify conductor.

---

## Setup for New Project

```bash
cd your-project

# Initialize beads
bd init

# Copy agent configs
git clone https://github.com/tsturo/debussy.git /tmp/debussy
mkdir -p .claude/subagents
cp /tmp/debussy/.claude/subagents/*.md .claude/subagents/
cp /tmp/debussy/CLAUDE.md .

# Start
debussy start
```

---

## Usage

Talk to conductor in the conductor pane:

```
I need user authentication with JWT.
```

Conductor will:
1. `debussy delegate "..."` → Create planning task for architect
2. Architect plans → creates implementation beads
3. `debussy assign bd-xxx developer` → Assign to developer (load-balanced)
4. Developer implements on feature branch
5. Sets status to `testing` → watcher spawns tester
6. Tester passes → status `reviewing` → watcher spawns reviewer
7. Reviewer approves → status `merging` → watcher spawns integrator
8. Integrator merges → status `acceptance` → watcher spawns tester
9. Tester does final verification → status `done`

---

## Commands

```bash
debussy start                    # Start tmux session
debussy start "requirement"      # Start with initial requirement
debussy delegate "requirement"   # Create planning task for architect
debussy assign bd-xxx developer  # Assign bead to agent
debussy status                   # Show pipeline progress
debussy inbox                    # Check conductor's messages
debussy trigger                  # Manual pipeline check
debussy watch                    # Run watcher only
debussy send agent "subject"     # Send message to agent
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  USER → @CONDUCTOR                                              │
│                                                                 │
│   requirement ──▶ delegates to @architect                       │
│                           │                                     │
│                           ▼                                     │
│                    beads created                                │
│                           │                                     │
│                           ▼                                     │
│         @conductor assigns from bd ready (load balanced)        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  PIPELINE (automated via watcher)                               │
│                                                                 │
│   in-progress ──▶ testing ──▶ reviewing ──▶ merging ──▶ acceptance ──▶ done
│        │            │            │             │            │
│     developer    tester      reviewer     integrator     tester
│        │            │            │             │
│        │            │            │             └── conflicts? → developer
│        │            │            └── changes requested? → developer
│        │            └── tests failed? → developer
│        │
│        └── implements on feature branch
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Git Workflow

```
main
└── develop
    ├── feature/bd-001-auth
    ├── feature/bd-002-login
    └── feature/bd-003-tokens
```

Commits reference beads: `[bd-001] Implement auth service`

---

## License

MIT
