# Project Instructions

## Overview

This project uses Beads (`bd`) for persistent task tracking across agent sessions. All work should be tracked in Beads, not markdown TODOs.

This file contains behavioral guidelines for all agents. Role-specific instructions are in `.claude/subagents/`.

---

## Core Principles

These principles reduce common LLM coding mistakes. All agents follow these unless their role explicitly overrides them.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

**Multi-agent rule:** If you discover ambiguity, file a Bead with `--status blocked` and state what needs clarification. Don't guess and proceed.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**Role exception:** @architect MAY identify overcomplications and recommend refactors — but via Beads, not direct changes.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated issues, **file a Bead** — don't fix silently.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the Bead you're working on.

**Multi-agent rule:** Discovered work outside your task scope? File a new Bead. Don't scope-creep your current task.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require clarification.

**Multi-agent rule:** Your Bead description IS your success criteria. If it's vague, ask @conductor for clarification before starting.

---

## Beads Workflow

### Starting a Session
```bash
bd ready                                    # See unblocked tasks
bd show <issue-id>                          # Read full task description
bd update <issue-id> --status in-progress   # Claim the task
```

Announce: "Working on bd-xxx: [description]"

### During Work
- **One task at a time.** Don't multitask across Beads.
- **File liberally.** Anything taking >2 minutes gets its own Bead.
- **Track blockers:** `bd update bd-xxx --status blocked --reason "..."`
- **Discovered work?** `bd create "Issue title" -p <priority>` — don't fix silently.

### Ending Work
Always "land the plane":
```bash
bd update <issue-id> --status done          # Mark complete
bd comment <issue-id> "Summary of changes"  # Document what was done
```

If tests pass, add label: `bd update <issue-id> --label passed`
If tests fail, add label: `bd update <issue-id> --label failed`

Handoffs are automated — completing a task triggers the next pipeline step.

---

## Subagents Available

Specialized agents for parallel work. Each has a dedicated role file in `.claude/subagents/`.

### @conductor (Entry Point)
- Single entry point for all work — user talks to conductor first
- Receives requirements, delegates planning to @architect/@designer
- Assigns tasks from `bd ready` after planning completes
- Monitors progress, triggers handoffs, handles escalations
- **Does not write code or make technical decisions**

### @architect
- Receives planning requests from @conductor
- Analyzes requirements, plans technical approach
- Breaks down requirements into tasks with dependencies
- Reviews code structure and design, creates ADRs
- **Does not write production code** — creates Beads

### @designer
- Receives planning requests from @conductor (for UI work)
- Plans UX flows, states, and accessibility requirements
- Collaborates with @architect during planning phase
- Reviews implemented UI for usability and accessibility
- **Does not write code** — creates Beads

### @developer
- Implements features and fixes bugs
- Writes production code with tests
- Follows all four principles strictly

### @tester
- Writes unit and integration tests
- Runs test suites, reports coverage
- **Emphasizes Principle #4:** Goal-driven, test-first execution

### @documenter
- Writes technical documentation
- Updates READMEs and API docs
- Only modifies documentation files

### @reviewer
- Code review for quality, security, performance
- **Uses Principle #3 as review criteria:** Flags unnecessary changes
- **Does not write code** — files Beads for issues found

### @integrator
- Merges branches, resolves conflicts
- Manages PRs and CI
- Closes parent tasks when integration completes

### @devops
- Manages CI/CD pipelines, Docker, Kubernetes
- Infrastructure as Code (Terraform, etc.)
- Deployment, monitoring, operational concerns

---

## Coordination Rules

### Who Does What

| Situation | Action | Who |
|-----------|--------|-----|
| New requirement received | Receive, delegate planning | @conductor |
| Planning needed | Analyze, create Beads | @architect + @designer |
| Tasks ready for assignment | Assign from `bd ready` | @conductor |
| Implementation work | Write code, tests | @developer |
| Code seems overcomplicated | File refactor Bead | @architect |
| UI/UX concerns | Review, file issues | @designer |
| Tests needed | Write tests | @tester |
| Review requested | Review, file issues | @reviewer |
| Ready to merge | Merge, resolve conflicts | @integrator |
| CI/CD or infra work | Pipelines, Docker, deploy | @devops |
| Docs outdated | Update docs | @documenter |
| Blocked on something | Update Bead status, notify | Any agent |
| Found unrelated bug | File new Bead | Any agent |

### What NOT To Do

- **Don't fix issues outside your current Bead** — file a new Bead instead
- **Don't skip the pipeline** — no direct merges without review (except P1 hotfixes)
- **Don't assume requirements** — ask or file blocked Bead
- **Don't refactor while implementing** — finish feature first, file refactor Bead

### Communication via Beads

Beads is the single source of truth. Use it for:
- Task descriptions and acceptance criteria
- Comments and questions
- Status updates
- Linking related work (`--refs`, `--parent`, `--blocks`)

Don't rely on verbal/chat communication — if it's not in Beads, it didn't happen.

---

## Pipeline Flow

```
USER → @conductor → delegates to @architect + @designer → beads created
                                                                  ↓
                                              @conductor assigns from bd ready
                                                                  ↓
EXECUTION:  feature → test → review → integration + docs → done
```

**Handoffs are automated.** When you mark a task `done`, the system creates the next task and assigns it.

### Pipeline Rules

| Completed Task | Next Task Created | Assigned To |
|----------------|-------------------|-------------|
| `planning` (done) | Tasks ready in `bd ready` | @conductor assigns |
| `feature` (done) | `test: [title]` | @tester |
| `test` (passed) | `review: [title]` | @reviewer |
| `test` (failed) | `bug: fix [title]` | @developer |
| `review` (approved) | `integration` + `docs` | @integrator, @documenter |
| `review` (changes requested) | Parent → in-progress | @developer |
| `bug` P1 (done) | `integration: hotfix` | @integrator |
| `integration` (done) | Closes parent | — |

### Labels for Pipeline Decisions

Add labels to guide automation:
```bash
bd update bd-xxx --label passed           # Tests passed
bd update bd-xxx --label failed           # Tests failed
bd update bd-xxx --label approved         # Review approved
bd update bd-xxx --label changes-requested # Needs fixes
```

---

## Code Standards

### General
- Follow existing patterns in the codebase
- Match existing style, even if you'd do it differently
- Write tests for new functionality
- Update documentation when changing public APIs

### Commit Messages
```
[bd-xxx] Brief description of change

- Detail 1
- Detail 2
```

### Branch Naming
```
feature/bd-xxx-short-description
bugfix/bd-xxx-short-description
hotfix/bd-xxx-short-description
```

---

## Project Structure

```
src/                    # Source code
tests/                  # Test files
docs/                   # Documentation
  adr/                  # Architecture Decision Records
.beads/                 # Beads database (git-tracked)
.claude/                # Claude Code settings
  subagents/            # Subagent role definitions
scripts/                # Automation scripts
  handoff-watcher.sh    # Automated pipeline
  handoff.sh            # Manual handoff helper
  start-agents.sh       # tmux workspace launcher
logs/                   # Handoff logs
config/                 # Configuration files
```

---

## Success Criteria

These guidelines are working if you see:

- ✓ Fewer unnecessary changes in diffs — only requested changes appear
- ✓ Fewer rewrites due to overcomplication — code is simple the first time
- ✓ Clarifying questions come before implementation — not after mistakes
- ✓ Clean pipeline flow — tasks move through stages without manual intervention
- ✓ No scope creep — discovered work becomes new Beads, not side fixes
- ✓ Clear audit trail — every change traces to a Bead
