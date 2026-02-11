# Project Instructions

## Overview

This project uses Beads (`bd`) for task tracking. The watcher automatically spawns agents based on **stage labels** on beads.

Role-specific instructions are in `.claude/subagents/`.

---

## Core Principles

### 1. Think Before Coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them.
- If something is unclear, stop and ask.

### 2. Simplicity First

- No features beyond what was asked.
- No abstractions for single-use code.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

- Don't "improve" adjacent code.
- Match existing style.
- If you notice unrelated issues, file a Bead — don't fix silently.

### 4. Goal-Driven Execution

- Transform tasks into verifiable goals.
- Strong success criteria let you work independently.

---

## Pipeline Flow

Two pipelines depending on task type:

```
Development:   open → stage:development → stage:reviewing → stage:testing → stage:merging → stage:acceptance → closed
Investigation: open → stage:investigating (parallel) → stage:consolidating (investigator) → .md file → conductor creates dev tasks → closed
```

Investigators research in parallel and document findings. A consolidation step (investigator) synthesizes findings into an .md file. Conductor then creates developer tasks.

**Status model:**

| bd status | Meaning |
|-----------|---------|
| `open` + stage label | Ready for agent |
| `open` (no stage label) | Backlog/parked |
| `in_progress` | Agent is working |
| `closed` | Pipeline complete |
| `blocked` | Waiting for deps / agent stuck |

**Stage transitions are owned by the watcher.** Agents only set status and optionally add the `rejected` label for failures. The watcher reads the bead state after the agent finishes and moves the stage label accordingly.

**Watcher spawns agents based on stage labels:**

| Stage Label | Agent Spawned |
|-------------|---------------|
| `stage:development` | developer |
| `stage:investigating` | investigator |
| `stage:consolidating` | investigator |
| `stage:reviewing` | reviewer |
| `stage:testing` | tester |
| `stage:merging` | integrator |
| `stage:acceptance` | tester |

**Parallelization:**
- Total agents capped by `max_total_agents` (default 8)

---

## Stage Transition Ownership

**The watcher owns ALL stage transitions.** Agents NEVER use `--add-label stage:*` or `--remove-label stage:*`.

### Agent signals (what agents set)

| Signal | Command | When |
|--------|---------|------|
| Claim | `--status in_progress` | Starting work |
| Success | `--status open` | Work complete (non-terminal) |
| Done | `--status closed` | Terminal (acceptance pass, investigation) |
| Rejected | `--status open --add-label rejected` | Failed review/test, needs rework |
| Blocked | `--status blocked` | Can't proceed, needs conductor |

### Watcher response (what watcher does when agent finishes)

| Bead state | Watcher action |
|------------|----------------|
| status=open, no rejected | Remove stage label, add NEXT_STAGE |
| status=open, rejected | Remove stage + rejected labels, add stage:development |
| status=closed | Remove stage label (done) |
| status=blocked | Remove stage label (parked for conductor) |

---

## Agents

### @conductor
- Entry point — user talks to conductor
- **First step**: creates a feature branch and registers it: `debussy config base_branch feature/<name>`
- Creates tasks with `bd create "title" -d "description"`
- Releases dev tasks: `bd update <id> --add-label stage:development`
- Releases investigation tasks: `bd update <id> --add-label stage:investigating`
- Creates all tasks first (backlog), then releases with `--add-label`
- Monitors progress with `debussy status`
- **Does not write code**
- **Never merges to master** — user does that manually

### @developer
- Implements features and fixes bugs
- Success: `--status open` (watcher advances to stage:reviewing)
- Blocked: `--status blocked` (watcher parks for conductor)

### @reviewer
- Reviews code for quality and security
- Approve: `--status open` (watcher advances to stage:testing)
- Reject: `--status open --add-label rejected` (watcher sends to stage:development)

### @tester
- Tests code
- Pass: `--status open` (watcher advances to stage:merging)
- Fail: `--status open --add-label rejected` (watcher sends to stage:development)
- Acceptance pass: `--status closed` (watcher removes stage label, done)
- Acceptance fail: `--status open --add-label rejected` (watcher sends to stage:development)

### @integrator
- Merges feature branches to conductor's base branch
- Success: `--status open` (watcher advances to stage:acceptance)
- Conflict: `--status open --add-label rejected` (watcher sends to stage:development)
- **Never merges to master**

### @investigator
- Researches codebase, documents findings as bead comments
- Does NOT create developer tasks
- Success: `--status closed` (watcher removes stage label)
- Also handles `stage:consolidating`: synthesizes findings into .md file

---

## Beads Workflow

### Creating Tasks
```bash
bd create "Implement feature X" -d "Description of what to do"
```

### Releasing Tasks (conductor only)
```bash
bd update <bead-id> --add-label stage:development     # development task
bd update <bead-id> --add-label stage:investigating   # investigation task
```

### Parallel Investigation (conductor only)
```bash
bd create "Investigate area A" -d "Research details"                                   # → bd-001
bd create "Investigate area B" -d "Research details"                                   # → bd-002
bd create "Consolidate findings" -d "Synthesize results" --deps "bd-001,bd-002"        # → bd-003
bd update bd-001 --add-label stage:investigating
bd update bd-002 --add-label stage:investigating
bd update bd-003 --add-label stage:consolidating
```
The consolidation bead stays blocked until all investigation beads finish.

---

## Code Standards

### Commit Messages
```
[bd-xxx] Brief description
```

### Branch Naming
```
feature/<name>       # conductor's base branch (created first)
feature/<bead-id>    # developer sub-branches (off conductor's branch)
```

### Branching Model
```
master (manual merge only by user)
  └── feature/<name>          ← conductor's branch
        ├── feature/bd-001    ← developer branch (merged back by integrator)
        ├── feature/bd-002
        └── feature/bd-003
```

Merging to master is NEVER done by agents — only by the user manually.

---

## Project Structure

```
src/debussy/
  watcher.py      # Spawns agents, owns stage transitions
  cli.py          # CLI commands
  config.py       # Configuration
  prompts/        # Agent prompt templates (per-agent files)
.claude/
  subagents/      # Agent role definitions
  hooks/          # Validation hooks
.beads/           # Beads database
```

---

## Commands

```bash
debussy start              # Start system (tmux)
debussy watch              # Run watcher
debussy status             # Show status
debussy config base_branch feature/<name>  # Set conductor's base branch
bd create "title" -d "description"
bd update <id> --add-label stage:development     # Release task for development
bd update <id> --add-label stage:investigating   # Release task for investigation
bd show <id>
bd list
```
