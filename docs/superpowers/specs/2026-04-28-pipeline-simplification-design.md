# Design: Bounded Integrator Conflict Resolution

**Date:** 2026-04-28 (revised after auditing origin state)
**Status:** Approved (design phase)
**Sequence:** Spec 1 of 3. Originally scoped as broader "pipeline simplification" but most of that work landed on origin in commit c2c19a4 (2026-04-06). What remains is the integrator change. See `2026-04-28-skills-followup-roadmap.md` for what comes after.

## Goal

Change the integrator agent from "reject on any conflict" to "resolve within bounded rules, block when bounds are exceeded." Today the integrator is essentially a script — it rejects any merge conflict back to development. If it stays as an LLM agent, it should earn its keep by attempting safe resolution. Unbounded LLM merge resolution is dangerous (silently-wrong semantic merges), so the rules must be operational, not aspirational.

## Background — what's already done

Origin commit `c2c19a4` (2026-04-06, "Revert enhanced review pipeline, keep dep unblock after merge, enrich reviewer prompt") and follow-ups already removed:

- The `skeptic`, `ux-reviewer`, `perf-reviewer`, and `arch-reviewer` prompts and all their config/code references (config.py, watcher.py `AGENT_ROLES`, spawner.py, prompts/__init__.py, transitions.py).
- The `STAGE_UX_REVIEW` and `STAGE_PERF_REVIEW` stages from `config.py`, including from `NEXT_STAGE`, `STAGE_TO_ROLE`, `STAGE_REQUIRED_TAGS` (constant deleted), `POST_MERGE_STAGES` (constant deleted), `STAGE_SHORT`, `ACCEPTANCE_ROLES` (constant deleted).
- `takt/db.py` CHECK constraint references to those stages.
- The corresponding sections in `CLAUDE.md` and `README.md`.

The reviewer prompt was also enriched with architecture and skeptic perspectives in that change. It now has 8 review categories (scope, code quality, correctness, security, frontend completeness, architecture, skeptic, tests) and explicitly states "any issue in the above categories is grounds for rejection" — which already addresses the "approve with follow-up tasks" failure mode the original full-scope spec was designed to prevent.

The integrator's "merge conflict → reject" path is the **only remaining** piece of the originally-bundled pipeline simplification that has not landed.

## Change

In `src/debussy/prompts/integrator.md`, replace lines 31-33:

```
IF MERGE CONFLICTS cannot be resolved:
  takt comment <TASK_ID> "Merge conflict: [details]"
  takt reject <TASK_ID>
```

with bounded resolution rules. The integrator prompt MUST contain operational definitions, not abstract rules — the model will rationalize past loose criteria.

### Auto-resolve allowed ONLY when conflicts are limited to

- **Non-overlapping hunks**: conflict markers (`<<<<<<<` ... `=======` ... `>>>>>>>`) in the same file are separated by at least one line of unmodified context. If markers are adjacent or interleaved, treat as same-block.
- **Pure formatting differences**: the conflicting hunks differ only in whitespace, trailing newlines, or quote style. Run `git diff -w` on the conflict region to confirm — if `-w` shows no diff, it is formatting-only.
- **Import statement additions**: both sides added new import lines and there are no removed imports anywhere in the conflict. Adding both sets is safe; never remove an import that any side added.

### Block (no resolution attempt, do not push) when ANY of

- Conflicts touch the **same logical block**: conflict markers fall between the same enclosing `def` / `function` / `class` / `func` declaration on both sides. Determination procedure: read the file from the conflict marker upward until the first such declaration is found. If determining the enclosing declaration requires reading more than 100 lines of context, OR the file has no `def` / `function` / `class` / `func` keywords above the conflict, treat as same-block and BLOCK. When in doubt, block.
- Conflicts in **test files** (paths matching `test_*.py`, `*_test.py`, `tests/**`, `*.spec.ts`, `*.test.ts`, `__tests__/**`).
- Conflicts in **lockfiles**: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `Gemfile.lock`, `go.sum`, `uv.lock`, `bun.lockb`.
- **Total conflict size > 20 lines**, defined as: sum of all lines between `<<<<<<<` and `>>>>>>>` markers across all files.

### After ANY non-trivial resolution

(Anything beyond pure formatting or import additions.) The integrator prompt MUST contain the explicit instruction:

> "EVERY Bash invocation that runs tests MUST include `timeout: 600000` (10 minutes). This applies to the initial run, retries, narrowed reruns, and single-test invocations alike. If tests do not complete in 10 minutes, re-run with `run_in_background: true` and use the Monitor tool to wait for completion. Do NOT use the default 2-minute Bash timeout — that will silently block the task on any non-trivial test suite."

If tests fail, block (do not push).

If no test command is auto-discoverable (no `pytest.ini`, `pyproject.toml [tool.pytest]`, `Makefile` test targets, or `package.json` test scripts), check for an operator-supplied override: `debussy config test_command` (a string the integrator runs verbatim instead of auto-discovery). If neither auto-discovery nor an override yields a command, block with: "no test command discoverable; set `debussy config test_command` to enable auto-resolve for this project."

### Existing reject paths preserved

The non-conflict reject paths in `integrator.md` stay unchanged:
- "developer never pushed" (line 7-10) — push absent on remote → reject.
- "push fails after retries" (lines 21-29) — push retry exhaustion → reject. Push failure is an environment issue, not a code conflict.

### CLAUDE.md update

The `@integrator` section in `CLAUDE.md` currently says:

```
- Success: `takt release <id>` (task done, acceptance happens in batch)
- Conflict: `takt reject <id>` (watcher sends to development)
```

Update to reflect bounded resolution:

```
- Success (clean merge or trivial auto-resolve): `takt release <id>`
- Conflict beyond auto-resolve bounds: `takt block <id>` (parks for conductor)
- Push failure / branch missing: `takt reject <id>` (watcher sends to development)
```

## Out of scope

- **Reviewer changes** — origin already enriched the reviewer with skeptic/architecture perspectives and the "any issue → reject" decision rule. Adding tag-conditional UX/perf checklists is YAGNI now that the post-merge stages are gone.
- **Schema migration** — origin's `takt/db.py` already has the cleaned CHECK constraint. No `_migrate()` change needed.
- **Skill extraction** — deferred to Spec 2 (see roadmap).
- **Tag delivery hardening** (`takt show --json`, `tags.py` single source of truth) — deferred to Spec 3.

## Acceptance criteria

1. `src/debussy/prompts/integrator.md` no longer contains the lines `IF MERGE CONFLICTS cannot be resolved: ... takt reject <TASK_ID>`. The conflict path goes to bounded resolution.
2. `integrator.md` contains the operational definitions verbatim (these are tested via static content assertions):
   - The literal string `"EVERY Bash invocation that runs tests MUST include \`timeout: 600000\`"`.
   - The literal string `"When in doubt, block"`.
   - The literal phrase `"no test command discoverable; set \`debussy config test_command\` to enable auto-resolve for this project"`.
   - The lockfile list including all 9 names listed above.
3. `debussy config test_command` is supported as a configuration key (the integrator's resolution path reads it). If `debussy config` already accepts arbitrary keys, no command-layer change needed; otherwise add a passthrough.
4. `CLAUDE.md` `@integrator` section updated to reflect the new conflict→block (instead of conflict→reject) behavior.
5. New tests cover the integrator's resolution-vs-block decision logic. Because the integrator is a prompt-driven LLM agent, behavioral tests against an LLM are out of CI scope. Tests are split into:
   - **Static content assertions** on `integrator.md`: greps for each required literal string in #2.
   - **Unit tests on any helper code introduced** (e.g., if a `parse_conflict_size()` or `is_same_logical_block()` helper is extracted into Python for testability, that helper has direct unit tests).
   - **Manual verification cases** documented in the implementation plan, to be exercised by the user once: same-block conflict blocks; non-overlapping hunks resolve and push; lockfile-conflict blocks; >20-line conflict blocks; no-test-command-and-no-override blocks; no-test-command-with-override uses the override.
6. Existing tests pass (`pytest`).

## Risks (acknowledged, not blocking)

- **LLM-judged "non-overlapping hunks" classification.** A model under time pressure may misclassify same-block conflicts as separate hunks. The "when in doubt, block" rule and the 20-line ceiling are the safety net. If misclassifications happen in practice, the response is to tighten the operational definitions in the prompt — not to revert the change.
- **Test discovery heuristic.** Projects with non-standard test setups will block the integrator on every non-trivial conflict. The `debussy config test_command` escape valve mitigates this, but operators must know to set it. Document in CLAUDE.md.
- **Implementer paraphrasing.** The required literal strings are tested via grep (acceptance criterion #2/#5). If an implementer paraphrases instead of copying verbatim, the tests fail and the issue surfaces immediately.
