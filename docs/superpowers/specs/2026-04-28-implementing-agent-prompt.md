# Implementing-Agent Prompt — Spec 1 (Bounded Integrator Conflict Resolution)

**Date:** 2026-04-28
**Use:** Paste the prompt block below as the first message in a fresh Claude Code session in the debussy repo. The agent runs autonomously through plan → review → implement → review → push, with code-review iterations between phases. No human approval gates.

## How to invoke

Open a Claude Code session at the repo root (`/Users/tomek/dev/debussy/`). Paste the entire fenced block below as the first message. The agent should not ask follow-up questions before starting; if it does, push back and tell it to begin.

## The prompt

```
You are implementing a single, focused spec in the debussy repository. Run this end-to-end without stopping for human approval. Use code-review subagents between phases to catch issues. Do not ask for decisions or permission — make reasonable judgment calls grounded in the spec and the codebase. The only legitimate reasons to stop are: (a) you discover the spec contradicts the current code state in a way that invalidates the design, or (b) a reasonable reading of the spec produces two materially different implementations and you cannot pick one from context.

## Spec to implement

`docs/superpowers/specs/2026-04-28-pipeline-simplification-design.md`

Read it fully before doing anything else. The spec is narrowly scoped: the only behavior change is the integrator agent's conflict handling, plus a small CLAUDE.md update. Skill extraction and other refinements are NOT in scope — see `docs/superpowers/specs/2026-04-28-skills-followup-roadmap.md` for what is deferred.

## Read these for context, in this order

1. The spec file above.
2. `CLAUDE.md` at the repo root — project conventions, pipeline model, agent roles. Pay attention to "Code Standards" (commit messages, branch naming) and "Stage Transition Ownership."
3. `src/debussy/prompts/integrator.md` — the file you're modifying.
4. `src/debussy/cli.py` and grep for `config` to see how `debussy config` works today, so you know whether `test_command` needs a passthrough or already works.
5. The existing tests under `tests/` — match the style and discovery convention (pytest).

## Branch setup

Cut a feature branch off master before any code changes:
- `git checkout master && git pull origin master`
- `git checkout -b feature/integrator-bounded-resolve`

Do NOT commit to master at any point. The user does the master merge manually.

## Phase 1 — Plan

Produce a written plan as a markdown file at `docs/superpowers/plans/2026-04-28-integrator-bounded-resolve-plan.md`. The plan covers:

- The exact diff to `src/debussy/prompts/integrator.md` (replace lines 31-33 conflict-reject path with the bounded resolution rules from the spec; preserve the existing "developer never pushed" and "push fails after retries" reject paths).
- Whether `debussy config test_command` needs a code change or already works (verify by reading the CLI; do not assume).
- The exact diff to `CLAUDE.md` `@integrator` section.
- The grep-based static content tests for the integrator prompt — list each assertion, name the file (suggest `tests/test_integrator_prompt_content.py`), and quote the exact strings being asserted (per spec acceptance criterion #2).
- Any helper code you plan to extract for direct unit testing (acceptance criterion #5 mentions this is optional — only do it if a helper has clear independent value, not for ceremony).
- The list of manual verification cases the user must exercise after merge (spec calls these out — produce the actual case list with steps).
- The order of edits and the order of test additions, so each commit is small and verifiable.

Commit the plan: `git add docs/superpowers/plans/2026-04-28-integrator-bounded-resolve-plan.md && git commit -m "..."` with a HEREDOC commit message ending with the standard Co-Authored-By trailer used in recent commits (check `git log` to match style).

### Phase 1 review iteration

After committing the plan, dispatch a code-review subagent (use whichever the session has access to in this priority order: `feature-dev:code-reviewer`, `pr-review-toolkit:code-reviewer`, `sdw:code-reviewer`, or a `general-purpose` agent with a code-review brief). Brief it to review the plan file specifically against the spec — not the spec itself. The review must check: (a) plan covers every acceptance criterion in the spec, (b) plan's proposed test assertions actually quote the literal strings from spec criterion #2, (c) plan does not propose changes outside the spec scope, (d) plan's edit order produces small reviewable commits.

Apply actionable findings to the plan. Skip findings that conflict with the spec. Re-commit the updated plan. Run the review once more if the first pass produced substantive changes; otherwise proceed.

## Phase 2 — Implement

Execute the plan. Each logical step gets its own commit:
1. Edits to `integrator.md`.
2. Edits to `CLAUDE.md` `@integrator` section.
3. New test file `tests/test_integrator_prompt_content.py` with the static content assertions.
4. Any helper code + its unit tests (only if the plan justified extraction).
5. Any `debussy config` changes (only if the verification in Phase 1 found they were needed).

Commit messages follow the project style (subject under 70 chars, body explains why). Stage files explicitly by name; never `git add .` or `-A`. Use a HEREDOC for each commit message and include the Co-Authored-By trailer.

Run `pytest` after each commit. If any test fails, stop and fix before continuing — do not commit broken state.

### Phase 2 review iteration

After all commits land on the feature branch, dispatch a code-review subagent (same priority list as Phase 1) to review the diff between `master` and `feature/integrator-bounded-resolve`. Brief it to check: (a) every spec acceptance criterion is met by the diff, (b) static content assertion tests actually run and pass, (c) no scope creep, (d) commit hygiene (small, named files, no secrets, no `git add .`), (e) the integrator prompt's required literal strings appear verbatim (run grep against the diff to confirm).

Apply actionable findings as additional commits. Re-run the reviewer once more after fixes if findings were substantive. Stop iterating once the reviewer reports no actionable findings or only nits.

## Push and report

After Phase 2 review converges:
- `git push -u origin feature/integrator-bounded-resolve`
- Report the branch name, the list of commits on it, the path to the plan file, and the manual verification cases the user must run before merging.
- Do NOT open a PR. Do NOT merge to master.

## Hard rules

- Do not "improve" adjacent code that's not in the spec.
- Do not add comments beyond what the spec requires.
- Do not add functionality the spec doesn't request.
- The integrator prompt MUST contain the literal strings from spec acceptance criterion #2 verbatim. Paraphrasing fails the grep tests by design.
- If you discover the spec is wrong about current code state (e.g., something is already done, a path doesn't exist, a constant has been renamed), stop and report — do not attempt to "fix" the spec yourself.
- Never run destructive git commands (force push, hard reset, branch -D) without explicit instruction.
- Never commit to master.
- Never skip pre-commit hooks.

Begin with Phase 1 now. No preamble, no clarifying questions.
```
