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
- Post-merge stages always advance regardless of findings — issues become follow-up tasks, never rejections

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
- Output: always releases the task. If issues found: creates follow-up task(s) and comments on original with cross-reference.

### Performance Reviewer (`perf-reviewer`)

- Trigger: `perf_review` tag
- Works on: base branch
- Checks: N+1 queries, missing pagination, unbounded loops/fetches, blocking I/O in async paths, missing indexes implied by query patterns, large payload construction, unnecessary serialization
- Output: same as UX reviewer — always releases, creates follow-ups if needed.

### Architecture Reviewer (`arch-reviewer`)

- Per-batch, runs in parallel during acceptance
- Discovers batch contents by reading the acceptance task's dependency list, then examines each task's commits on the base branch
- Checks: cross-task coupling, duplicated responsibilities, data model consistency, bypassed abstractions, new patterns that conflict with existing ones, missing shared infrastructure
- Output: approve or create follow-up tasks + comments on relevant originals. Architecture issues don't block acceptance — test failures do.

### Skeptic (`skeptic`)

- Per-batch, runs in parallel during acceptance
- Discovers batch contents same way as arch-reviewer (reads dependency list)
- Reads all task descriptions + diffs
- Checks: does the batch deliver what the user originally asked for? Logical gaps? Unstated assumptions? Features that don't connect? Over-engineering vs. under-delivery?
- Output: same as arch-reviewer — follow-up tasks, not blocking.

### Tester (enhanced)

- Per-batch, runs in parallel during acceptance
- Existing behavior: runs full test suite
- New: before running tests, evaluates test quality — brittleness, implementation-coupling, missing edge cases, coverage gaps between tasks, descriptive naming
- Test suite pass/fail still blocks acceptance. Test quality issues create follow-up tasks, they don't block.

### Reviewer (narrowed)

- Remove security checks section (lines 42-47 in current prompt, including the "SECURITY" header) — security-reviewer handles that for tagged tasks
- Note: tasks without the `security` tag will have no dedicated security review. This is intentional — the existing reviewer's security checks were superficial and created a false sense of coverage. Tasks that need real security review should be tagged.
- Keeps: scope check, code quality, correctness, naming, structure, test-criteria verification

## Post-merge reviewers creating follow-up tasks

New capability for post-merge and acceptance agents: they can call `takt create` to generate follow-up tasks. Flow:

1. `takt create "Fix: <issue>" -d "Found during <review_type> of <TASK_ID>: <details>"`
2. `takt comment <TASK_ID> "<review_type>: found issue, follow-up task <NEW_ID>"`
3. `takt release <TASK_ID>`

Follow-up tasks land in backlog **without tags**. The conductor triages them and adds appropriate tags when advancing to development.

## Conductor Tagging Rules

Mandatory tagging checklist for every task. The conductor MUST evaluate every task against this list:

| Tag | Apply when |
|-----|-----------|
| `security` | User input handling, auth, crypto/secrets, dynamic file paths, DB queries with dynamic input, deserialization |
| `frontend` | UI/visual tasks |
| `ux_review` | Any task with `frontend` tag — always co-applied |
| `perf_review` | Task touches: database queries, API endpoints, file I/O, data processing loops, async operations, caching, network calls |

Not tagging is a deliberate decision that a review type doesn't apply — not forgetting.

Additionally, as a safety net: if a task has the `frontend` tag but is missing `ux_review`, `takt advance` should auto-add `ux_review`. This prevents silent skipping if the conductor forgets.

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

Currently dependencies check `stage == "done"`. Change to: dependencies are satisfied when stage is past `merging`.

Define a set of "post-merge" stages:
```python
POST_MERGE_STAGES = {STAGE_UX_REVIEW, STAGE_PERF_REVIEW, STAGE_DONE}
```

Dependency is satisfied when `task["stage"] in POST_MERGE_STAGES`.

**Two locations must be updated:**
1. `takt/log.py` — `get_unresolved_deps()` (line ~128): change `t.stage != 'done'` to `t.stage NOT IN ('ux_review', 'perf_review', 'done')`
2. `pipeline_checker.py` — `get_unmerged_dep_branches()` (line ~24): change `dep_task["stage"] == "done"` check to use `POST_MERGE_STAGES`

## Parallel Acceptance Agents

### Spawning

When the acceptance task becomes ready, the watcher spawns 3 agents (tester, arch-reviewer, skeptic) for the same task simultaneously.

The `STAGE_TO_ROLE` mapping changes for acceptance: instead of mapping to a single role, acceptance maps to `ACCEPTANCE_ROLES`:

```python
ACCEPTANCE_ROLES = ["tester", "arch-reviewer", "skeptic"]
```

`pipeline_checker.py` must handle this: when scanning the acceptance stage, spawn all three roles instead of one. The `is_task_running` check must be role-aware — don't skip spawning agent #2 just because agent #1 is already running for the same task.

### Tracking completion

Each agent gets its own entry in `watcher.running` keyed by `role:task_id` (e.g., `tester:PRJ-5`, `arch-reviewer:PRJ-5`, `skeptic:PRJ-5`).

In `cleanup_finished`: when an acceptance agent finishes, check if other agents are still running for the same task_id in the acceptance stage. Only advance to `done` when all have finished.

Pseudocode:
```python
def _all_acceptance_agents_done(watcher, task_id):
    return not any(
        a.task == task_id and a.spawned_stage == STAGE_ACCEPTANCE
        for a in watcher._alive_agents()
    )
```

### Failure handling

If one acceptance agent dies/times out but others succeed: the failed agent follows existing retry logic (increment `failures`, retry up to `MAX_RETRIES`). The successful agents' results stand. The task doesn't advance until all three have completed successfully or the failed one is blocked.

### State serialization

`save_state()` currently keys by `agent.task`. Change to key by `agent.name` (which is unique) to support multiple agents per task. The state file becomes a list of agent entries rather than a task-keyed dict.

## Transition Logic Changes

### `_TERMINAL_STAGES` update

Currently `_TERMINAL_STAGES = {STAGE_MERGING, STAGE_ACCEPTANCE}`. Merging is no longer terminal — it conditionally advances to post-merge stages.

```python
_TERMINAL_STAGES = {STAGE_ACCEPTANCE}
```

Merging completion now flows through `_handle_agent_success` → `_compute_next_stage` with tag-gated logic, same as other non-terminal stages.

### Updated `NEXT_STAGE` map

```python
NEXT_STAGE = {
    STAGE_BACKLOG: STAGE_DEVELOPMENT,
    STAGE_DEVELOPMENT: STAGE_REVIEWING,
    STAGE_REVIEWING: STAGE_MERGING,
    STAGE_SECURITY_REVIEW: STAGE_MERGING,
    STAGE_MERGING: STAGE_UX_REVIEW,      # default; tag-gating may skip
    STAGE_UX_REVIEW: STAGE_PERF_REVIEW,   # default; tag-gating may skip
    STAGE_PERF_REVIEW: STAGE_DONE,
    STAGE_ACCEPTANCE: STAGE_DONE,
}
```

### Tag-gated advancement

`_compute_next_stage` gains tag-skipping logic: after computing the default next stage from `NEXT_STAGE`, check if the task has the required tag. If not, skip to the next stage recursively until a matching stage or `done` is reached.

```python
# Tags required for each stage (absent = always runs)
STAGE_REQUIRED_TAGS = {
    STAGE_UX_REVIEW: "ux_review",
    STAGE_PERF_REVIEW: "perf_review",
}
```

### Merge verification

The existing `_verify_merge_landed` check stays at the merging stage. Branch deletion stays at merging completion. Both happen before any post-merge stage.

## Worktree Strategy for New Roles

Post-merge reviewers (`ux-reviewer`, `perf-reviewer`) and acceptance reviewers (`arch-reviewer`, `skeptic`) all work on the base branch. They use the same worktree strategy as the existing `tester` and `integrator`:

```python
# In create_agent_worktree:
elif r in ("reviewer", "security-reviewer"):
    return str(create_worktree(name, f"origin/feature/{bid}", detach=True))
elif r in ("integrator", "tester", "ux-reviewer", "perf-reviewer", "arch-reviewer", "skeptic"):
    return str(create_worktree(name, f"origin/{b}", detach=True))
```

## Config Changes

```python
STAGE_UX_REVIEW = "ux_review"
STAGE_PERF_REVIEW = "perf_review"

STAGE_TO_ROLE = {
    STAGE_ACCEPTANCE: "tester",  # primary role; ACCEPTANCE_ROLES handles multi-spawn
    STAGE_MERGING: "integrator",
    STAGE_SECURITY_REVIEW: "security-reviewer",
    STAGE_REVIEWING: "reviewer",
    STAGE_DEVELOPMENT: "developer",
    STAGE_UX_REVIEW: "ux-reviewer",
    STAGE_PERF_REVIEW: "perf-reviewer",
}

ACCEPTANCE_ROLES = ["tester", "arch-reviewer", "skeptic"]

STAGE_SHORT = {
    ...
    STAGE_UX_REVIEW: "ux",
    STAGE_PERF_REVIEW: "perf",
}

# Default model assignments for new roles
# Post-merge reviewers: sonnet (cost-efficient, reading-only tasks)
# Acceptance reviewers: opus (need deeper reasoning for cross-task analysis)
"role_models": {
    ...
    "ux-reviewer": "claude-sonnet-4-6",
    "perf-reviewer": "claude-sonnet-4-6",
    "arch-reviewer": "claude-opus-4-6",
    "skeptic": "claude-opus-4-6",
}

"max_role_agents": {
    ...
    "ux-reviewer": 10,
    "perf-reviewer": 10,
    "arch-reviewer": 1,   # one per batch
    "skeptic": 1,          # one per batch
}
```

## Files to Change

- `config.py` — new stages, stage constants, `STAGE_TO_ROLE`, `NEXT_STAGE`, `STAGE_SHORT`, `STAGE_REQUIRED_TAGS`, `ACCEPTANCE_ROLES`, `POST_MERGE_STAGES`, default `role_models` and `max_role_agents`
- `transitions.py` — remove `STAGE_MERGING` from `_TERMINAL_STAGES`, add tag-gated skipping to `_compute_next_stage`, update `_handle_agent_success` for post-merge flow, add `_all_acceptance_agents_done` check
- `takt/log.py` — update `get_unresolved_deps` to use `POST_MERGE_STAGES` for dependency satisfaction, update `advance_task` to support tag-gated next-stage computation
- `pipeline_checker.py` — update `get_unmerged_dep_branches` dependency check, handle multi-role spawning for acceptance stage, make `is_task_running` role-aware for acceptance
- `spawner.py` — add new roles to `create_agent_worktree` dispatch, support multi-agent spawning for acceptance
- `watcher.py` — add new roles to `AGENT_ROLES`, update `save_state` to key by agent name, add multi-agent completion tracking for acceptance
- `board.py` — add `ux_review` and `perf_review` columns
- `preflight.py` — add preflight checks for new roles (verify base branch exists for post-merge reviewers)
- `takt/cli.py` — ensure `--tags` flag support on `takt create`, add auto-tag safety net to `takt advance` (auto-add `ux_review` when `frontend` present)
- `prompts/reviewer.md` — remove security section (lines 42-47 including header)
- `prompts/tester.md` — add test quality evaluation before running test suite
- `prompts/conductor.md` — add mandatory tagging rules checklist
- **New:** `prompts/ux-reviewer.md`
- **New:** `prompts/perf-reviewer.md`
- **New:** `prompts/arch-reviewer.md`
- **New:** `prompts/skeptic.md`

## What Doesn't Change

- Developer, integrator, security-reviewer prompts — untouched
- Branch model — unchanged
- Task creation/advancement CLI — unchanged (except auto-tag safety net in `takt advance`)
- Watcher core run loop — unchanged (dispatch logic changes are in transitions/pipeline_checker)
