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
Development:   planning → open → developer → reviewing → reviewer → testing → tester → merging → integrator → acceptance → tester → done
Investigation: planning → investigating → investigator → done
```

Investigators research the problem and create developer tasks directly.

**Watcher spawns agents based on status:**

| Status | Agent Spawned |
|--------|---------------|
| planning | none (conductor is planning) |
| open | developer |
| investigating | investigator |
| reviewing | reviewer |
| testing | tester |
| merging | integrator |
| acceptance | tester |

**Parallelization:**
- Max 3 developers, investigators, testers, reviewers can run simultaneously
- Integrator is singleton (to avoid merge conflicts)

---

## Agents

### @conductor
- Entry point — user talks to conductor
- Creates tasks with `bd create "title" --status planning`
- Releases dev tasks: `bd update <id> --status open`
- Releases investigation tasks: `bd update <id> --status investigating`
- Monitors progress with `debussy status`
- **Does not write code**

### @investigator
- Researches codebase, documents findings as bead comments
- Creates developer tasks with `--status open` based on findings
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

### @integrator
- Merges feature branches to develop
- Sets `--status acceptance` after merge

---

## Beads Workflow

### Creating Tasks
```bash
bd create "Implement feature X" --status planning
```

### Releasing Tasks (conductor only)
```bash
bd update <bead-id> --status open            # development task
bd update <bead-id> --status investigating   # investigation task
```

### Status Transitions

Investigator:
```bash
bd create "Dev task from findings" --status open   # create dev tasks
bd update <bead-id> --status done                  # complete investigation
```

Developer:
```bash
bd update <bead-id> --status testing
```

Tester:
```bash
bd update <bead-id> --status reviewing   # pass
bd update <bead-id> --status open     # fail (add comment first)
```

Reviewer:
```bash
bd update <bead-id> --status merging     # approved
bd update <bead-id> --status open     # changes needed
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
feature/<bead-id>
```

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
bd create "title" --status planning
bd update <id> --status open            # Release task for development
bd update <id> --status investigating   # Release task for investigation
bd update <id> --status <status>
bd show <id>
bd list
```
