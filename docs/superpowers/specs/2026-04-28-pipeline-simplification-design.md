# Design: Pipeline Simplification

**Date:** 2026-04-28
**Status:** Approved (design phase)
**Sequence:** This is Spec 1 of 3. See `2026-04-28-skills-followup-roadmap.md` for what comes after.

## Goal

Simplify debussy's agent pipeline before any skill-extraction work:

1. Drop the `skeptic` agent (its job belongs to conductor and reviewer).
2. Fold `ux-reviewer` and `perf-reviewer` into `reviewer` via task tags — eliminate two stages.
3. Change integrator from "reject on conflict" to "resolve within bounds, block on failure."

These changes simplify the pipeline regardless of whether skills get extracted later.

## Change 1: Drop `skeptic`

### Rationale

`skeptic` runs at batch acceptance to ask "did we build the right thing?" That question belongs upstream — to the conductor when defining tasks, and the reviewer when checking per-task scope. By the time skeptic runs post-merge, any "intent gap" finding represents a failure in task definition, not a problem skeptic can fix. Findings only generated follow-up tasks (never blocked acceptance), so the agent existed to produce backlog noise.

### Implementation

- Delete `src/debussy/prompts/skeptic.md`.
- Remove `"skeptic"` entry from `_ROLE_FILES` and `_ROLE_DOC_FOCUS` in `src/debussy/prompts/__init__.py`.
- Remove `"skeptic"` from `ACCEPTANCE_ROLES` in `src/debussy/config.py`.
- Remove `"skeptic"` from `role_models` defaults in `config.py`.
- Remove `"skeptic"` from `max_role_agents` defaults in `config.py`.
- Remove `"skeptic"` from the hardcoded role tuple in `src/debussy/spawner.py:60-61` (`create_agent_worktree`).
- Remove `"skeptic"` from `AGENT_ROLES` in `src/debussy/watcher.py:123-124`.
- Update `CLAUDE.md` to remove the skeptic role description and the "tester + arch-reviewer + skeptic in parallel" mention.
- Update tests that reference skeptic spawning (search `tests/` for the string).

The acceptance batch becomes `tester + arch-reviewer` running in parallel.

## Change 2: Fold `ux-reviewer` and `perf-reviewer` into `reviewer`

### Rationale

`ux_review` and `perf_review` were post-merge non-blocking stages — they only filed follow-ups. That's a smell: if the findings matter, they should block before merge; if they don't, the agent is busywork. Folding the checklists into the per-task reviewer (gated by task tags) lets the same expertise actually block, removes two stages from the state machine, and reduces total agent spawns.

### Implementation

**Reviewer prompt update (`src/debussy/prompts/reviewer.md`):**

The reviewer prompt gains a tag-conditional checklist section. The existing reviewer checklist runs unconditionally. Two new conditional sections — UX checklist and perf checklist — execute only when the task has the corresponding tag.

The checklists themselves come directly from the existing `ux-reviewer.md` and `perf-reviewer.md` (move the checklist bodies, drop the lifecycle preamble). Rename them in-context to "UX REVIEW (when `ux_review` tag present)" and "PERFORMANCE REVIEW (when `perf_review` tag present)."

Crucially: in the new reviewer, findings from these sections **block on the same terms as correctness findings**. They are no longer informational. The reviewer prompt MUST contain the explicit instruction:

> "Treat UX and performance findings identically to correctness findings. Any blocking issue from any section means REJECT. Do NOT approve with follow-up tasks for blocking issues."

**Tag parsing (explicit in the prompt):**

Tags already arrive in the agent's user message via `get_user_message()` in `src/debussy/prompts/__init__.py` (`Tags: <comma-separated>`). The reviewer reads tags from there. The prompt MUST instruct tag extraction explicitly to avoid silent skips:

> "Find the line in your user message that begins with `Tags:`. If no such line exists, treat as having no tags and skip both conditional sections. Otherwise: take everything after `Tags:`, split on `,`, trim whitespace from each token, lowercase, and check for the exact tokens `ux_review` and `perf_review`. No substring matching."

Improving tag delivery (structured access via `takt show --json`) is deferred to a follow-up spec.

**`_ROLE_DOC_FOCUS` update:**

The reviewer's entry in `_ROLE_DOC_FOCUS` (`src/debussy/prompts/__init__.py`) currently reads "architecture, conventions, and constraints to validate implementation choices." Update it to reflect the expanded scope (e.g., "architecture, conventions, constraints, and — when tagged — UX and performance considerations").

**Stage and config removal:**

- Delete `src/debussy/prompts/ux-reviewer.md` and `src/debussy/prompts/perf-reviewer.md`.
- Remove `"ux-reviewer"` and `"perf-reviewer"` entries from `_ROLE_FILES` and `_ROLE_DOC_FOCUS`.
- Remove the `STAGE_UX_REVIEW` and `STAGE_PERF_REVIEW` constants from `config.py`.
- Remove these stages from `NEXT_STAGE`, `STAGE_TO_ROLE`, `STAGE_REQUIRED_TAGS`, `POST_MERGE_STAGES`, and `STAGE_SHORT` maps.
- Remove `"ux-reviewer"` and `"perf-reviewer"` from `role_models`, `max_role_agents`, and the spawner.py:60-61 role tuple.
- Remove `"ux-reviewer"` and `"perf-reviewer"` from `AGENT_ROLES` in `src/debussy/watcher.py:123-124`.
- Update `transitions.py` to remove any lookups, branches, or guards keyed on the removed stages. Specifically: any references to `STAGE_UX_REVIEW`, `STAGE_PERF_REVIEW`, `'ux_review'`, or `'perf_review'` must be deleted (not silently left behind), and any logic that uses `STAGE_REQUIRED_TAGS` to gate entry into those stages must be removed entirely. After the change, grep the file for the removed stage names and confirm zero matches.
- Update `CLAUDE.md`: remove the two stages from the pipeline diagram, remove the agent role descriptions, remove the post-merge tag-gated stages explanation.

**Conductor prompt update (`src/debussy/prompts/conductor.md`):**

The conductor's tagging matrix already includes `ux_review` and `perf_review` tags — the rules stay the same (still co-apply `ux_review` with `frontend`; still apply `perf_review` to anything touching DB queries, API endpoints, etc.). What changes is the downstream effect: the tags now extend the reviewer's checklist instead of triggering separate post-merge stages. Update the conductor prompt's explanation accordingly.

**IMPORTANT consequence to surface in the conductor prompt:** these tags now drive **blocking** review sections, not informational post-merge ones. Resolve the apparent contradiction with the existing matrix as follows:

- **`ux_review`**: keep the auto-co-apply rule with `frontend`. Frontend tasks intend UX-blocking by definition — if a frontend task ships without working accessibility/responsive behavior, that's a defect. The auto-rule is correct.
- **`perf_review`**: the conductor should apply this **deliberately**, not reflexively. Apply it when the task touches code paths where a perf regression should block merge (e.g., a hot DB query, a request-handler loop). Do NOT apply it to pure CRUD glue or one-off scripts where theoretical N+1s aren't worth gating on. Add this clarification to the conductor prompt's matrix.

### Migration for in-flight tasks and DB schema

The `tasks.stage` column has a `CHECK` constraint in `src/debussy/takt/db.py` (constructor at lines 24-25 and inside the v4 `_migrate` branch around lines 162-181) that hardcodes `'ux_review'` and `'perf_review'` as valid stage values. Removing the stages from Python code without updating the schema leaves the constraint stale; new SQLite databases would still accept those stage strings.

**Use takt's existing versioned migration mechanism** (`takt/db.py:101-182`, `_migrate()`, `SCHEMA_VERSION`):

1. Bump `SCHEMA_VERSION` from 4 to 5.
2. Add a `version < 5` branch in `_migrate()` (mirror the v4 branch's table-recreate pattern) that:
   - First, for each task currently at `ux_review` or `perf_review`, append a log entry via takt's existing log mechanism (e.g., `INSERT INTO task_log` or whatever the existing API uses) recording: "stage migrated to done by schema v5 (post-merge stages removed)". This preserves audit trail for operators.
   - Then runs the data update: `UPDATE tasks SET stage = 'done' WHERE stage IN ('ux_review', 'perf_review')`. This advances any in-flight tasks before the new constraint would reject them. Safe because these were always non-blocking post-merge stages.
   - Then recreates the `tasks` table (rename old, create new without `'ux_review'`/`'perf_review'` in the CHECK constraint, copy data over, drop old).
3. Update the constructor's CHECK constraint (lines 24-25) to match the v5 set.
4. Bump `SCHEMA_VERSION` accordingly.

The migration runs automatically on watcher startup via the existing `init_db()` → `get_db()` → `_apply_schema()` → `_migrate()` chain. No standalone script needed.

## Change 3: Integrator resolves conflicts (within bounds), does not reject

### Rationale

Today the integrator rejects any merge conflict, sending the task back to development. That makes the integrator essentially a script — there's no LLM judgment involved. If we keep the integrator as an agent, it should earn its keep by attempting safe conflict resolution. But unbounded LLM merge resolution is dangerous (silently-wrong semantic merges).

### Implementation

Update `src/debussy/prompts/integrator.md` so the conflict path becomes:

The integrator prompt MUST contain operational definitions, not abstract rules. The model will rationalize past loose criteria.

**Auto-resolve allowed ONLY when conflicts are limited to:**
- **Non-overlapping hunks**, defined as: conflict markers (`<<<<<<<` ... `=======` ... `>>>>>>>`) in the same file are separated by at least one line of unmodified context. If markers are adjacent or interleaved, treat as same-block.
- **Pure formatting differences**, defined as: the conflicting hunks differ only in whitespace, trailing newlines, or quote style. Run `git diff -w` on the conflict region to confirm — if `-w` shows no diff, it is formatting-only.
- **Import statement additions**, defined as: both sides added new import lines and there are no removed imports anywhere in the conflict. Adding both sets is safe; never remove an import that any side added.

**Block (no resolution attempt, do not push) when ANY of:**
- Conflicts touch the **same logical block**, defined as: conflict markers fall between the same enclosing `def` / `function` / `class` / `func` declaration on both sides. Determination procedure: read the file from the conflict marker upward until the first such declaration is found. If determining the enclosing declaration requires reading more than 100 lines of context, OR the file has no `def` / `function` / `class` / `func` keywords above the conflict, treat as same-block and BLOCK. When in doubt, block.
- Conflicts in **test files** (paths matching `test_*.py`, `*_test.py`, `tests/**`, `*.spec.ts`, `__tests__/**`, etc.) — semantic test changes are too risky to auto-resolve.
- Conflicts in **lockfiles**: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `Gemfile.lock`, `go.sum`, `uv.lock`, `bun.lockb`.
- **Total conflict size > 20 lines**, defined as: sum of all lines between `<<<<<<<` and `>>>>>>>` markers across all files.

**After ANY non-trivial resolution** (anything beyond pure formatting or import additions), the integrator MUST run the project's test suite locally before pushing. The integrator prompt MUST instruct the agent explicitly:

> "EVERY Bash invocation that runs tests MUST include `timeout: 600000` (10 minutes). This applies to the initial run, retries, narrowed reruns, and single-test invocations alike. If tests do not complete in 10 minutes, re-run with `run_in_background: true` and use the Monitor tool to wait for completion. Do NOT use the default 2-minute Bash timeout — that will silently block the task on any non-trivial test suite."

If tests fail, block (do not push). If no test command is auto-discoverable (no `pytest.ini`, `pyproject.toml [tool.pytest]`, `Makefile` test targets, or `package.json` test scripts), check for an operator-supplied override: `debussy config test_command` (a string the integrator runs verbatim instead of auto-discovery). If neither auto-discovery nor an override yields a command, block with the explanation "no test command discoverable; set `debussy config test_command` to enable auto-resolve for this project." This avoids permanent stalls on projects with non-standard test setups while keeping the safe-by-default behavior.

**Replace the existing "merge conflict → reject" path** with the above. The "push fails after retries" path can still reject (push retry exhaustion is an environment issue, not a code conflict).

## Out of scope (deferred to later specs)

- Skill extraction (`dbs-*` skills). See `2026-04-28-skills-followup-roadmap.md`.
- Skill output contracts and verdict tokens.
- Skill distribution (install command, symlinks, preflight).
- A `tags.py` single-source-of-truth module.
- Adding `takt show --json` or otherwise structured tag delivery.
- Moving any other reviewer expertise into reusable artifacts.

## Acceptance criteria

1. `src/debussy/prompts/skeptic.md`, `ux-reviewer.md`, and `perf-reviewer.md` are deleted.
2. `src/debussy/prompts/__init__.py` no longer has `skeptic`, `ux-reviewer`, or `perf-reviewer` in `_ROLE_FILES` or `_ROLE_DOC_FOCUS`.
3. `src/debussy/config.py` no longer has `STAGE_UX_REVIEW` or `STAGE_PERF_REVIEW`; they are removed from `NEXT_STAGE`, `STAGE_TO_ROLE`, `STAGE_REQUIRED_TAGS`, `POST_MERGE_STAGES`, `STAGE_SHORT`. Removed roles are gone from `ACCEPTANCE_ROLES`, `role_models`, `max_role_agents`.
4. `src/debussy/spawner.py` no longer references `ux-reviewer`, `perf-reviewer`, or `skeptic` in the `create_agent_worktree` role tuple (or anywhere else). `src/debussy/watcher.py` `AGENT_ROLES` set (lines 123-124) no longer contains those roles.
5. `src/debussy/transitions.py` does not reference any of the removed stages.
6. `src/debussy/prompts/reviewer.md` includes UX and performance checklist sections that execute conditionally based on the `ux_review` and `perf_review` tags read from the user message. The prompt contains explicit, literal tag-parsing instructions (find `Tags:` line, split on `,`, trim, lowercase, exact-token match — no substring matching). Findings from those sections **block on the same terms as correctness findings**, and the prompt explicitly states: "Any blocking issue from any section means REJECT. Do not approve with follow-up tasks for blocking issues."
7. `src/debussy/prompts/__init__.py` `_ROLE_DOC_FOCUS["reviewer"]` is updated to reflect the expanded scope.
8. `src/debussy/prompts/conductor.md` is updated so the tag-policy paragraph reflects that `ux_review` and `perf_review` extend the reviewer rather than triggering post-merge stages. The conductor prompt also explicitly states: apply these tags only when issues found there should actually block merge, not for cosmetic concerns.
9. `src/debussy/prompts/integrator.md` no longer has a "merge conflict → reject" path. It contains operational resolution rules (concrete definitions of non-overlapping hunks, logical block, lockfile list, conflict-size measurement) and an explicit Bash timeout instruction (10-minute timeout with `run_in_background` + Monitor fallback).
10. The takt schema is migrated to v5: `SCHEMA_VERSION` bumped, a `version < 5` branch in `_migrate()` advances in-flight `ux_review`/`perf_review` tasks to `done` and recreates the `tasks` table without those stages in the CHECK constraint. Constructor CHECK constraint at `takt/db.py:24-25` updated to match.
11. `CLAUDE.md` is updated: skeptic removed from agent list; ux-reviewer and perf-reviewer removed from agent list; pipeline diagram no longer shows the two post-merge stages; the watcher's stage→agent table no longer mentions them.
12. Existing tests pass (`pytest`). Tests referencing removed roles/stages are updated or deleted. New tests cover:
    - **Static content assertions on prompt files** (the prompt files are `.md`, not Python; tests grep the file content for required literal strings):
      - `reviewer.md` contains the literal string "Any blocking issue from any section means REJECT".
      - `reviewer.md` contains the literal tag-parsing instruction starting with "Find the line in your user message that begins with `Tags:`".
      - `integrator.md` contains the literal string "EVERY Bash invocation that runs tests MUST include `timeout: 600000`".
      - `integrator.md` contains the literal string "When in doubt, block".
      - `conductor.md` contains the perf_review deliberateness clarification.
    - Integrator's resolution-vs-block decision logic — at minimum: a same-block-conflict case blocks; a non-overlapping-hunk case resolves and pushes; a lockfile-conflict case blocks; a >20-line-conflict case blocks; a no-test-command-and-no-override case blocks; a no-test-command-with-override case uses the override.
    - Migration correctness: insert tasks at `ux_review` and `perf_review` against a v4 schema, run the migration, assert tasks land at `done`, the audit log entries exist, and the new schema rejects insertion of those stage values.
    - `AGENT_ROLES` and `_ROLE_FILES` no longer contain the removed roles.

13. The `debussy config` command supports a new `test_command` key (read-only consumer is the integrator's resolution path). If `debussy config` already supports arbitrary keys, no command change needed; otherwise add a passthrough for this key.

## Risks (acknowledged, not blocking)

- **Reviewer scope creep:** loading two more checklists when both `ux_review` and `perf_review` tags are present makes a dense reviewer. We accept this for Spec 1; if review quality degrades in practice, the next spec (skill extraction) gives us a tool to split it back out.
- **Integrator test discovery:** the integrator's "find and run tests" step is heuristic. For projects with non-standard test commands, the integrator will block rather than push silently — this is the desired failure mode but may surprise users. Document in `CLAUDE.md` that integrator may block when test commands aren't auto-discoverable.
- **Tag-from-user-message is fragile:** if the user message format changes, the reviewer's tag parsing breaks. Tracked in the followup roadmap.
