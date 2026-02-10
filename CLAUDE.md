# Project Instructions

## Overview

This project uses Beads (`bd`) for task tracking. The watcher automatically spawns agents based on bead status.

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
Development:   planning → development → developer → reviewing → reviewer → testing → tester → merging → integrator → acceptance → tester → done
Investigation: planning → investigating (parallel) → consolidating (investigator) → .md file → conductor creates dev tasks → done
```

Investigators research in parallel and document findings. A consolidation step (investigator) synthesizes findings into an .md file. Conductor then creates developer tasks.

**Watcher spawns agents based on status:**

| Status | Agent Spawned |
|--------|---------------|
| planning | none (conductor is planning) |
| open | none (parked, waiting for conductor) |
| development | developer |
| investigating | investigator |
| consolidating | investigator |
| reviewing | reviewer |
| testing | tester |
| merging | integrator |
| acceptance | tester |

**Parallelization:**
- Total agents capped by `max_total_agents` (default 6)

---

## Agents

### @conductor
- Entry point — user talks to conductor
- **First step**: creates a feature branch and registers it: `debussy config base_branch feature/<name>`
- Creates tasks with `bd create "title" --status planning`
- Releases dev tasks: `bd update <id> --status development`
- Releases investigation tasks: `bd update <id> --status investigating`
- Creates all tasks as `planning` first, then releases with `bd update`
- Monitors progress with `debussy status`
- **Does not write code**
- **Never merges to master** — user does that manually

### @investigator
- Researches codebase, documents findings as bead comments
- Does NOT create developer tasks (consolidation step handles that)
- Sets `--status done` when investigation complete

### @developer
- Implements features and fixes bugs
- Sets `--status testing` when done

### @tester
- Tests code
- Sets `--status reviewing` if pass, `--status open` if fail

### @reviewer
- Reviews code for quality and security
- Sets `--status merging` if approved, `--status open` if changes needed

### @investigator
- Also handles `consolidating` status: synthesizes investigation findings into .md file for conductor

### @integrator
- Merges feature branches to conductor's base branch (status `merging`)
- Sets `--status acceptance` after merge
- **Never merges to master**

---

## Beads Workflow

### Creating Tasks
```bash
bd create "Implement feature X" -d "Description of what to do" --status planning
```

### Releasing Tasks (conductor only)
```bash
bd update <bead-id> --status development     # development task
bd update <bead-id> --status investigating   # investigation task
```

### Parallel Investigation (conductor only)
```bash
bd create "Investigate area A" --status planning               # → bd-001
bd create "Investigate area B" --status planning               # → bd-002
bd create "Consolidate findings" --deps "bd-001,bd-002" --status planning  # → bd-003
bd update bd-001 --status investigating
bd update bd-002 --status investigating
bd update bd-003 --status consolidating
```
The consolidation bead stays blocked until all investigation beads finish.

### Status Transitions

Investigator:
```bash
bd comment <bead-id> "Finding: [details]"          # document findings
bd update <bead-id> --status done                  # complete investigation
```

Investigator (consolidation):
```bash
# Write findings to .debussy/investigations/<bead-id>.md
bd comment <bead-id> "Investigation complete — see .debussy/investigations/<bead-id>.md"
bd update <bead-id> --status done                  # complete consolidation
```

Developer:
```bash
bd update <bead-id> --status reviewing
```

Reviewer:
```bash
bd update <bead-id> --status testing     # approved
bd update <bead-id> --status open     # changes needed
```

Tester:
```bash
bd update <bead-id> --status merging   # pass
bd update <bead-id> --status open     # fail (add comment first)
```

Integrator:
```bash
bd update <bead-id> --status acceptance
```

Tester (acceptance):
```bash
bd update <bead-id> --status done        # pass
bd update <bead-id> --status open     # fail
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
  watcher.py      # Spawns agents based on status
  cli.py          # CLI commands
  config.py       # Configuration
.claude/
  subagents/      # Agent role definitions
.beads/           # Beads database
```

---

## Commands

```bash
debussy start              # Start system (tmux)
debussy watch              # Run watcher
debussy status             # Show status
debussy config base_branch feature/<name>  # Set conductor's base branch
bd create "title" --status planning
bd update <id> --status development     # Release task for development
bd update <id> --status investigating   # Release task for investigation
bd update <id> --status <status>
bd show <id>
bd list
```
