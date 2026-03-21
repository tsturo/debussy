# Enhanced Review Pipeline

## Problem

The current reviewer is a generalist — it checks code quality, correctness, security, frontend completeness, and tests in one pass. This creates several gaps:

- No UX/design judgment beyond element-existence checklists
- No architecture review for cross-task coupling, data model fit, or pattern consistency
- Shallow test quality evaluation (only checks criteria listed in task description)
- No business logic validation ("does this solve the right problem?")
- No performance review (N+1 queries, unbounded fetches, blocking I/O)

## Design

### Two-tier review model

**Tier 1 — Pre-merge (blocking):** The existing reviewer gates the pipeline. Its scope is narrowed to code quality and correctness (security checks removed since security-reviewer handles tagged tasks).

**Tier 2 — Post-merge (non-blocking per-task) + batch acceptance:**
- Per-task post-merge stages for UX and performance review, gated by tags
- Batch-level acceptance expanded with architecture, skeptic, and test quality reviewers running in parallel

Post-merge reviews don't block the pipeline. Dependencies unblock after merging. If post-merge reviewers find issues, they create follow-up tasks in backlog and comment on the original task. The conductor triages follow-ups.

### Per-task pipeline

```
backlog → development → reviewing → [security_review] → merging → [ux_review] → [perf_review] → done
                                     ^security tag        ^deps     ^ux_review    ^perf_review
                                                          unblock   tag           tag
```

- `[bracketed]` stages are skipped if the task lacks the corresponding tag
- Dependencies unblock when a task exits `merging` (not `done`)
- Feature branch is deleted after merging as before — post-merge reviewers work on the base branch

### Batch acceptance (parallel)

```
acceptance task (deps on all batch tasks) → tester + arch-reviewer + skeptic (parallel) → done
```

Three agents spawn simultaneously for one acceptance task. The watcher advances to `done` only when all three finish.

### Tag-gated stage skipping

When the watcher advances a task past `merging`, it checks tags:
- Has `ux_review` tag → advance to `ux_review`
- No `ux_review` tag, has `perf_review` tag → skip to `perf_review`
- Neither tag → skip straight to `done`

After `ux_review` completes:
- Has `perf_review` tag → advance to `perf_review`
- No `perf_review` tag → advance to `done`

## Agent Roster

| Agent | Type | Stage | Blocking? | New/Modified |
|-------|------|-------|-----------|--------------|
| Developer | Per-task | development | Yes | Unchanged |
| Reviewer | Per-task | reviewing | Yes | Modified (security checks removed) |
| Security Reviewer | Per-task | security_review | Yes | Unchanged |
| Integrator | Per-task | merging | Yes | Unchanged |
| UX Reviewer | Per-task | ux_review | No (deps already open) | **New** |
| Perf Reviewer | Per-task | perf_review | No (deps already open) | **New** |
| Tester | Per-batch | acceptance | Yes | Modified (test quality evaluation added) |
| Architecture Reviewer | Per-batch | acceptance | Yes | **New** |
| Skeptic | Per-batch | acceptance | Yes | **New** |

### UX Reviewer (`ux-reviewer`)

- Trigger: `ux_review` tag (conductor sets on all `frontend` tasks)
- Works on: base branch (code already merged)
- Checks: design spec compliance (reads ref file from task description), accessibility (semantic HTML, ARIA, keyboard nav, contrast), responsive behavior, UX anti-patterns (inconsistent interactions, dead-end flows, missing loading/error states)
- Output: approve (comment + release) or create follow-up task + comment on original

### Performance Reviewer (`perf-reviewer`)

- Trigger: `perf_review` tag
- Works on: base branch
- Checks: N+1 queries, missing pagination, unbounded loops/fetches, blocking I/O in async paths, missing indexes implied by query patterns, large payload construction, unnecessary serialization
- Output: approve or create follow-up task + comment on original

### Architecture Reviewer (`arch-reviewer`)

- Per-batch, runs in parallel during acceptance
- Reads all task diffs in the batch against the base branch
- Checks: cross-task coupling, duplicated responsibilities, data model consistency, bypassed abstractions, new patterns that conflict with existing ones, missing shared infrastructure
- Output: approve or create follow-up tasks + comments on relevant originals

### Skeptic (`skeptic`)

- Per-batch, runs in parallel during acceptance
- Reads all task descriptions + diffs
- Checks: does the batch deliver what the user originally asked for? Logical gaps? Unstated assumptions? Features that don't connect? Over-engineering vs. under-delivery?
- Output: approve or create follow-up tasks + comments on relevant originals

### Tester (enhanced)

- Per-batch, runs in parallel during acceptance
- Existing behavior: runs full test suite
- New: before running tests, evaluates test quality — brittleness, implementation-coupling, missing edge cases, coverage gaps between tasks, descriptive naming
- Test quality issues create follow-up tasks, they don't block acceptance (test pass/fail still blocks)

### Reviewer (narrowed)

- Remove security checks section (lines 43-47 in current prompt) — security-reviewer handles that for tagged tasks
- Keeps: scope check, code quality, correctness, naming, structure, test-criteria verification

## Post-merge reviewers creating follow-up tasks

New capability for post-merge and acceptance agents: they can call `takt create` to generate follow-up tasks. Flow:

1. `takt create "Fix: <issue>" -d "Found during <review_type> of <TASK_ID>: <details>"`
2. `takt comment <TASK_ID> "<review_type>: found issue, follow-up task <NEW_ID>"`
3. `takt release <TASK_ID>`

Follow-up tasks land in backlog. Conductor picks them up and triages as usual.

## Conductor Tagging Rules

Mandatory tagging checklist for every task. The conductor MUST evaluate every task against this list:

| Tag | Apply when |
|-----|-----------|
| `security` | User input handling, auth, crypto/secrets, dynamic file paths, DB queries with dynamic input, deserialization |
| `frontend` | UI/visual tasks |
| `ux_review` | Any task with `frontend` tag — always co-applied |
| `perf_review` | Task touches: database queries, API endpoints, file I/O, data processing loops, async operations, caching, network calls |

Not tagging is a deliberate decision that a review type doesn't apply — not forgetting.

Examples:
```bash
# Backend API endpoint
takt create "Add GET /api/users" -d "..." --tags perf_review

# Frontend page
takt create "Build settings page" -d "..." --tags frontend,ux_review

# Frontend page that fetches data
takt create "Build dashboard with analytics" -d "..." --tags frontend,ux_review,perf_review

# Auth endpoint
takt create "Add JWT validation middleware" -d "..." --tags security,perf_review

# Pure config/types/glue — no enhanced review tags
takt create "Add TypeScript types for User model" -d "..."
```

## Dependency Unblocking

Currently dependencies check `stage == "done"`. Change to: dependencies are satisfied when `stage` is past `merging` (i.e., in `ux_review`, `perf_review`, or `done`).

This ensures post-merge reviews don't block dependent tasks.

## Parallel Acceptance Agents

When the acceptance task becomes ready, the watcher spawns 3 agents (tester, arch-reviewer, skeptic) for the same task simultaneously. Each gets its own entry in `watcher.running` keyed by `role:task_id`. The watcher advances acceptance to `done` only when no agents remain running for that task.

## Config Changes

```python
STAGE_UX_REVIEW = "ux_review"
STAGE_PERF_REVIEW = "perf_review"

STAGE_TO_ROLE = {
    ...
    STAGE_UX_REVIEW: "ux-reviewer",
    STAGE_PERF_REVIEW: "perf-reviewer",
}

ACCEPTANCE_ROLES = ["tester", "arch-reviewer", "skeptic"]
```

`role_models` and `max_role_agents` defaults updated to include new roles.

## Files to Change

- `config.py` — new stages, role mappings, defaults
- `transitions.py` — tag-gated skipping, dependency unblock logic, parallel acceptance tracking
- `pipeline_checker.py` — updated dependency resolution
- `spawner.py` — multi-agent spawning for acceptance
- `board.py` — new stage columns
- `prompts/reviewer.md` — remove security section
- `prompts/tester.md` — add test quality evaluation
- `prompts/conductor.md` — add tagging rules
- **New:** `prompts/ux-reviewer.md`
- **New:** `prompts/perf-reviewer.md`
- **New:** `prompts/arch-reviewer.md`
- **New:** `prompts/skeptic.md`

## What Doesn't Change

- Developer, integrator, security-reviewer prompts — untouched
- Branch model — unchanged
- Task creation/advancement CLI — unchanged
- Watcher core loop — unchanged (new dispatch logic in transitions)
