# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer.*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           YOU                                    │
│                            ↓                                     │
│                      @conductor                                  │
│                    (always running)                              │
│                            ↓                                     │
│                    python -m debussy                             │
│                   ┌───────┴───────┐                             │
│                   ↓               ↓                              │
│              mailbox           beads                             │
│            (file-based)       (tasks)                            │
│                   ↓                                              │
│               watcher                                            │
│         (spawns agents on demand)                                │
│                   ↓                                              │
│    ┌──────┬──────┼──────┬──────┬──────┐                         │
│    ↓      ↓      ↓      ↓      ↓      ↓                         │
│ architect dev1  dev2  tester reviewer integrator                │
│                                                                  │
│        Agents start when needed, exit when done                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# 1. Install prerequisites
brew install beads  # Task tracking
# Python 3.10+ required

# 2. Install Debussy
brew install pipx && pipx ensurepath
pipx install git+https://github.com/tsturo/debussy.git

# 3. Start in your project
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
Run as @conductor. I need user authentication with JWT.
```

Conductor will:
1. `python -m debussy delegate "..."` → Create planning task
2. Architect plans → creates implementation beads
3. `python -m debussy assign bd-xxx developer` → Assign to developer
4. Developer implements on feature branch
5. Pipeline: test → review → integration
6. Each agent spawns when needed, exits when done

---

## Commands

```bash
python -m debussy start                    # Start system
python -m debussy delegate "requirement"   # Plan with architect
python -m debussy assign bd-xxx developer  # Assign bead
python -m debussy status                   # System status
python -m debussy inbox                    # Check responses
python -m debussy send agent "subject"     # Send message
python -m debussy watch                    # Run watcher only
```

---

## Project Structure

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
│              @conductor assigns from bd ready                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  EXECUTION                                                      │
│                                                                 │
│   feature ──▶ test ──▶ review ──▶ integration ──▶ done         │
│      │          │         │            │                        │
│      │          │         │            └──▶ docs (parallel)     │
│      │          │         │                                     │
│      │          │         └──▶ changes requested? → developer   │
│      │          │                                               │
│      │          └──▶ failed? → developer (bug fix)              │
│      │                                                          │
│      └──▶ @developer implements                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Roles

| Role | Purpose | Writes Code |
|------|---------|-------------|
| **conductor** | Creates/assigns tasks | ❌ |
| **architect** | Plans, creates beads | ❌ |
| **developer** | Implements on branches | ✅ |
| **tester** | Writes/runs tests | ✅ |
| **reviewer** | Reviews, files issues | ❌ |
| **integrator** | Merges branches | ✅ |

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
