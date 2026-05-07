# Plan: Bounded Integrator Conflict Resolution

**Spec:** `docs/superpowers/specs/2026-04-28-pipeline-simplification-design.md`
**Branch:** `feature/integrator-bounded-resolve`
**Date:** 2026-04-28

## Goal

Replace the integrator's "any conflict → reject" path with bounded resolution rules; everything else (push retry, missing-remote-branch reject) stays as-is. Add `test_command` as a known config key so the integrator's resolution path can fall back to an operator-supplied test command. Update `CLAUDE.md` `@integrator` section. Add static content tests on the integrator prompt.

## Verification of current code state

- `src/debussy/prompts/integrator.md` — lines 31-33 contain the conflict-reject path verbatim as quoted in the spec. Lines 7-10 (developer never pushed) and lines 21-29 (push retry exhaustion) are preserved as the spec requires.
- `src/debussy/cli.py` `cmd_config` (line 109) — accepts arbitrary key/value pairs via `set_config`. There is no per-key validation in `set_config` itself (`config.py` line 195).
- However, `clean_config()` (`config.py` line 203) deletes any key not in `KNOWN_KEYS`, and `cmd_start` calls `clean_config()` on every `debussy start` (`cli.py` line 46). `KNOWN_KEYS` (`config.py` line 156) does NOT currently contain `test_command`, which means an operator who runs `debussy config test_command 'pytest -q'` would have it silently wiped on the next `debussy start`.
- Conclusion: the spec's "if `debussy config` already accepts arbitrary keys, no command-layer change needed" branch does not apply here — `test_command` MUST be added to `KNOWN_KEYS` to survive `clean_config()`. This is a one-line config change, not a CLI change.
- `CLAUDE.md` `@integrator` section is at lines 137-141 of the current file (header at 137, the two bullets to replace at 139-140) and contains the "Conflict: `takt reject <id>`" line that the spec replaces.

## Edits

### Edit 1 — `src/debussy/prompts/integrator.md`

Replace the existing lines 31-34 block:

```
IF MERGE CONFLICTS cannot be resolved:
  takt comment <TASK_ID> "Merge conflict: [details]"
  takt reject <TASK_ID>
  Exit
```

with the following bounded resolution rules. Required literal strings from spec acceptance criterion #2 are quoted verbatim and appear as a single contiguous block (so each grep hits a stable location). Operational definitions match the spec word-for-word in the bullet bodies:

```
IF MERGE CONFLICTS:
  Attempt auto-resolve ONLY when ALL conflicts in the merge satisfy at least one of:
    - Non-overlapping hunks: conflict markers (<<<<<<<, =======, >>>>>>>) in the same
      file are separated by at least one line of unmodified context. If markers are
      adjacent or interleaved, treat as same-block.
    - Pure formatting differences: the conflicting hunks differ only in whitespace,
      trailing newlines, or quote style. Run `git diff -w` on the conflict region —
      if `-w` shows no diff, it is formatting-only.
    - Import statement additions: both sides added new import lines and there are no
      removed imports anywhere in the conflict. Adding both sets is safe; never remove
      an import that any side added.

  BLOCK (no resolution attempt, do not push) when ANY of the following holds:
    - Conflicts touch the same logical block: conflict markers fall between the same
      enclosing `def` / `function` / `class` / `func` declaration on both sides. Read
      the file from the conflict marker upward until the first such declaration is
      found. If determining the enclosing declaration requires reading more than 100
      lines of context, OR the file has no `def` / `function` / `class` / `func`
      keywords above the conflict, treat as same-block and BLOCK. When in doubt, block.
    - Conflicts in test files (paths matching `test_*.py`, `*_test.py`, `tests/**`,
      `*.spec.ts`, `*.test.ts`, `__tests__/**`).
    - Conflicts in lockfiles: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`,
      `poetry.lock`, `Cargo.lock`, `Gemfile.lock`, `go.sum`, `uv.lock`, `bun.lockb`.
    - Total conflict size > 20 lines, defined as the sum of all lines between
      `<<<<<<<` and `>>>>>>>` markers across all files.

  When blocking:
    takt comment <TASK_ID> "Merge conflict beyond auto-resolve bounds: [details]"
    takt block <TASK_ID>
    Exit

  After ANY non-trivial resolution (anything beyond pure formatting or import
  additions), run the project test suite before pushing.

  EVERY Bash invocation that runs tests MUST include `timeout: 600000` (10 minutes).
  This applies to the initial run, retries, narrowed reruns, and single-test
  invocations alike. If tests do not complete in 10 minutes, re-run with
  `run_in_background: true` and use the Monitor tool to wait for completion. Do NOT
  use the default 2-minute Bash timeout — that will silently block the task on any
  non-trivial test suite.

  If tests fail after a non-trivial resolution:
    takt comment <TASK_ID> "Tests failed after conflict resolution: [details]"
    takt block <TASK_ID>
    Exit

  Test command discovery: use `pytest` if `pytest.ini`, `pyproject.toml [tool.pytest]`,
  or any `tests/` directory exists; otherwise `make test` if a `Makefile` defines a
  `test` target; otherwise `npm test` if `package.json` defines a `test` script.
  If none of those apply, check for an operator-supplied override:
  `debussy config test_command` (a string the integrator runs verbatim instead of
  auto-discovery). If neither auto-discovery nor an override yields a command, block:
    takt comment <TASK_ID> "no test command discoverable; set `debussy config test_command` to enable auto-resolve for this project"
    takt block <TASK_ID>
    Exit
```

The previously-existing `IF PUSH FAILS` block (lines 21-29) and the developer-never-pushed reject (lines 7-10) are NOT touched.

### Edit 2 — `src/debussy/config.py`

In `KNOWN_KEYS` (line 156), add `"test_command"` to the set. Single-line addition. No other change. This is the minimum to make `debussy config test_command '<cmd>'` survive `clean_config()`.

### Edit 3 — `CLAUDE.md`

Locate the `@integrator` section. Replace these two lines:

```
- Success: `takt release <id>` (task done, acceptance happens in batch)
- Conflict: `takt reject <id>` (watcher sends to development)
```

with:

```
- Success (clean merge or trivial auto-resolve): `takt release <id>` (task done, acceptance happens in batch)
- Conflict beyond auto-resolve bounds: `takt block <id>` (parks for conductor)
- Push failure / branch missing: `takt reject <id>` (watcher sends to development)
```

The "Never merges to master" line and the bullet structure stay.

### Edit 4 — `tests/test_integrator_prompt_content.py` (new file)

A pure-Python test that reads `src/debussy/prompts/integrator.md` from disk and asserts the spec-required literal substrings appear verbatim. Style matches existing test files (pytest, no class wrapper needed for simple read-and-assert).

Assertions (each is a `assert <literal> in content` style check, exact substring match):

1. `EVERY Bash invocation that runs tests MUST include \`timeout: 600000\`` — the literal string from spec criterion #2 bullet 1, including the backticks around `timeout: 600000`.
2. `When in doubt, block` — spec criterion #2 bullet 2.
3. ``no test command discoverable; set `debussy config test_command` to enable auto-resolve for this project`` — spec criterion #2 bullet 3, including the backticks around `debussy config test_command`.
4. Each of the 9 lockfile names individually as substrings: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `Gemfile.lock`, `go.sum`, `uv.lock`, `bun.lockb`. Done as a parametrized loop or 9 separate asserts; either is acceptable. Keep them as separate asserts so a missing one names itself in the failure.
5. The old reject path is gone: assert `Merge conflict: [details]` does NOT appear and `takt reject` is NOT preceded by a "MERGE CONFLICTS cannot be resolved" line. The simpler form: assert the substring `IF MERGE CONFLICTS cannot be resolved` is absent.
6. Confirm the preserved reject paths still exist: `origin/feature/<TASK_ID> does not exist` and `Push failed after retries` substrings present.

The file resolves the prompt path via `pathlib.Path(__file__).resolve().parents[1] / "src" / "debussy" / "prompts" / "integrator.md"` so the test runs regardless of cwd.

## Helper extraction

Not doing it. The spec's acceptance criterion #5 calls helper extraction optional and ties it to "clear independent value." All the conflict-classification logic lives inside the LLM prompt; there is no Python code path consuming a parsed conflict list. Extracting `parse_conflict_size()` or `is_same_logical_block()` would be ceremony — the helpers would have no caller. Skip.

## Edit / commit order

Each step is its own commit. After each commit, run `pytest` and confirm green before the next.

1. **Add the static-content test file first** (`tests/test_integrator_prompt_content.py`). This commit alone fails the test (the prompt hasn't been updated yet) — so the actual sequence is to write the test in the same commit as the prompt edit, OR write the test file, run it once locally to confirm it fails as expected, then fold the prompt edit into the next commit. Choosing the simpler version: **commits 1 and 2 below are bundled into a single commit** that adds both the failing-then-passing assertions and the prompt change. Rationale: a deliberately-failing intermediate commit on `master`'s history is more confusing than helpful, and the static-content test has no value separated from the prompt it tests.
2. **Commit A — `prompts/integrator.md` + `tests/test_integrator_prompt_content.py`** together. Subject: `Replace integrator conflict-reject with bounded auto-resolve`. After commit, `pytest tests/test_integrator_prompt_content.py` must pass.
3. **Commit B — `src/debussy/config.py`** add `test_command` to `KNOWN_KEYS`. Subject: `Allow test_command as a known config key`. After commit, full `pytest` must pass.
4. **Commit C — `CLAUDE.md`** `@integrator` section update. Subject: `Document integrator block-on-conflict behavior`. No test change.

All commits use plain-prose subject lines (no bracketed prefix) to match the style of recent spec-related commits on master (`Narrow pipeline simplification spec to integrator change only`, `Add pipeline simplification spec and skills roadmap`). The `CLAUDE.md` `[PRJ-N]` convention applies to in-pipeline takt tasks; this work is outside the takt pipeline so plain prose is the correct match. All commits use a HEREDOC body and end with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer matching recent commits. Files staged by name; no `git add .` / `-A`.

## Manual verification cases (for the user post-merge)

To be exercised once after merge, by simulating each scenario in a feature branch and walking the integrator prompt logic:

1. **Same-block conflict blocks.** Create two branches that both edit the same function body in `src/debussy/cli.py`; merge one, then run integrator on the other. Expected: `takt block`, no push.
2. **Non-overlapping hunks resolve and push.** Create two branches that edit different functions in the same file (separated by ≥1 unmodified line). Expected: integrator resolves, runs tests, pushes, releases.
3. **Lockfile conflict blocks.** Conflict in `uv.lock` (or any of the 9 listed lockfiles). Expected: `takt block`, no push, regardless of conflict size.
4. **>20-line conflict blocks.** Even a non-overlapping conflict whose total marker-to-marker span exceeds 20 lines. Expected: `takt block`.
5. **No test command discoverable + no override.** In a synthetic project with no `pytest.ini`, no `Makefile`, no `package.json`, and `debussy config test_command` unset. Expected: `takt block` with the literal "no test command discoverable…" message.
6. **No test command discoverable + override set.** Same project as case 5 but with `debussy config test_command 'true'` set. Expected: integrator runs `true`, tests "pass," push proceeds.
7. **Test command override survives `debussy start`.** Run `debussy config test_command 'pytest -q'`, then `debussy start`, then `debussy config test_command`. Expected: value still `pytest -q` (this is what Edit 2 to `KNOWN_KEYS` enables).

Cases 1-4 exercise classification rules; cases 5-6 exercise the test-command fallback; case 7 exercises the config persistence change.

## Out of scope (per spec)

- Reviewer prompt changes — already enriched in origin commit `c2c19a4`.
- Schema migrations — already done in origin.
- Skill extraction — Spec 2.
- `takt show --json` / `tags.py` — Spec 3.
- Any helper Python code (skipped, see above).
