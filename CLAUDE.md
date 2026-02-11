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
| `blocked` | Waiting for deps |

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

**Agent workflow:** claim with `--status in_progress` → work → set next stage label + `--status open` (or `--status closed` for final stage)

**Parallelization:**
- Total agents capped by `max_total_agents` (default 6)

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

### @investigator
- Researches codebase, documents findings as bead comments
- Does NOT create developer tasks (consolidation step handles that)
- Finishes with `--remove-label stage:investigating --status closed`

### @developer
- Implements features and fixes bugs
- Finishes with `--remove-label stage:development --add-label stage:reviewing --status open`

### @tester
- Tests code
- Pass: `--remove-label stage:testing --add-label stage:merging --status open`
- Fail: `--remove-label stage:testing --add-label stage:development --status open`

### @reviewer
- Reviews code for quality and security
- Approve: `--remove-label stage:reviewing --add-label stage:testing --status open`
- Reject: `--remove-label stage:reviewing --add-label stage:development --status open`

### @investigator (consolidation)
- Handles `stage:consolidating`: synthesizes investigation findings into .md file for conductor

### @integrator
- Merges feature branches to conductor's base branch (`stage:merging`)
- Finishes with `--remove-label stage:merging --add-label stage:acceptance --status open`
- **Never merges to master**

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

### Stage Transitions

Investigator:
```bash
bd comment <bead-id> "Finding: [details]"
bd update <bead-id> --remove-label stage:investigating --status closed
```

Investigator (consolidation):
```bash
# Write findings to .debussy/investigations/<bead-id>.md
bd comment <bead-id> "Investigation complete — see .debussy/investigations/<bead-id>.md"
bd update <bead-id> --remove-label stage:consolidating --status closed
```

Developer:
```bash
bd update <bead-id> --remove-label stage:development --add-label stage:reviewing --status open
```

Reviewer:
```bash
bd update <bead-id> --remove-label stage:reviewing --add-label stage:testing --status open     # approved
bd update <bead-id> --remove-label stage:reviewing --add-label stage:development --status open  # changes needed
```

Tester:
```bash
bd update <bead-id> --remove-label stage:testing --add-label stage:merging --status open   # pass
bd update <bead-id> --remove-label stage:testing --add-label stage:development --status open  # fail
```

Integrator:
```bash
bd update <bead-id> --remove-label stage:merging --add-label stage:acceptance --status open
```

Tester (acceptance):
```bash
bd update <bead-id> --remove-label stage:acceptance --status closed        # pass
bd update <bead-id> --remove-label stage:acceptance --add-label stage:development --status open  # fail
```

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
  watcher.py      # Spawns agents based on stage labels
  cli.py          # CLI commands
  config.py       # Configuration
  prompts.py      # Agent prompt templates
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
