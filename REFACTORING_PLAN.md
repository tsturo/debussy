# Refactoring Plan

## Executive Summary

The debussy codebase (2,687 lines across 14 files) has two monolithic files: `cli.py` (961 lines) and `watcher.py` (831 lines). These files mix data access, domain logic, process management, and UI rendering into single modules with long methods (up to 107 lines, 5 nesting levels). Code is duplicated across files (`_get_bead_status` exists twice, dependency-checking logic under two names, symlink cleanup repeated 3 times). Domain concepts like pipeline stages are scattered as raw strings across five separate mapping dictionaries that must be kept in sync manually. There are 30+ instances of bare `except Exception: pass` silently swallowing errors, and a shell injection risk in tmux agent spawning.

This plan addresses these problems in 4 phases (~18 tasks): extract shared code and fix safety issues, break up the two monoliths into focused modules, tighten domain modeling with string constants and co-located mappings, and add type safety plus tests for the critical paths. Each phase ends with a smoke test before proceeding.

## Current State Assessment

| File | Lines | Key Issues |
|------|-------|------------|
| `cli.py` | 961 | 13 command handlers + board rendering + bead queries + tmux management + metrics |
| `watcher.py` | 831 | Agent lifecycle + 107-line state machine + bead queries + worktree setup + events + orphan cleanup |
| `worktree.py` | 236 | Symlink cleanup block duplicated 3 times, raw subprocess calls |
| `config.py` | 116 | Mixes runtime config with domain constants (STAGE_TO_ROLE, NEXT_STAGE) |
| `prompts/__init__.py` | 45 | Inconsistent builder signatures requiring lambda wrappers |
| `__init__.py` | 6 | Eagerly imports Watcher, triggering `os.environ.pop` side effect |

**Duplicated code:**
- `_get_bead_status` -- identical logic in `cli.py:529` and `watcher.py:79`
- `_waiting_on` (cli.py:194) and `_has_unresolved_deps` (watcher.py:95) -- same logic, different names
- `_dep_summary` (cli.py:239) -- duplicates dependency iteration logic from `_waiting_on`
- Symlink removal block repeated 3 times in worktree.py (lines 102-105, 200-202, 226-229)
- Stage mappings in 5 places: `STAGE_TO_ROLE` (config.py:25), `NEXT_STAGE` (config.py:35), `STAGE_SHORT` (cli.py:654), `BOARD_STAGE_MAP` (cli.py:678), `BOARD_COLUMNS` (cli.py:665)

**Longest methods:**
- `_ensure_stage_transition` -- 107 lines, 5 nesting levels (watcher.py:570-676)
- `cmd_metrics` -- 93 lines (cli.py:869-961)
- `check_pipeline` -- 75 lines, 7 `continue` conditions in nested loop (watcher.py:458-532)
- `_render_vertical` -- 44 lines (cli.py:796-839)
- `cleanup_finished` -- 40 lines (watcher.py:741-780)

**Other issues:**
- 30+ bare `except Exception: pass` -- silent error swallowing throughout
- Shell injection risk: bead_id interpolated into shell string (watcher.py:302-303)
- `_has_unmerged_dep_branches` returns `list` but name implies `bool`
- Fallback prompt in prompts/__init__.py silently produces a vague prompt instead of erroring

---

## Phase 1: Foundation -- Extract Shared Code, Fix Safety Issues

Goal: Eliminate duplication, create a single place to access bead data, fix the security issue. This unblocks all later phases.

**Smoke test after completion:** `debussy watch` runs for 60 seconds without crashing; `debussy status` prints output; `debussy board` renders correctly.

### Task 1.1: Fix eager Watcher import in `__init__.py`
**Effort:** S
`__init__.py` imports `Watcher` at module level, which triggers `os.environ.pop("ANTHROPIC_API_KEY", None)` as a side effect on any import. Remove the eager import. Only expose `__version__`.

**Acceptance:** `import debussy` has no side effects. `Watcher` is imported where needed (cli.py already does this lazily).

### Task 1.2: Create `bead_client.py` with cross-module bead functions
**Effort:** M
Extract bead subprocess calls that are duplicated or used across modules into `src/debussy/bead_client.py`:
- `get_bead_json(bead_id)` -- from watcher.py:65
- `get_bead_status(bead_id)` -- deduplicate from cli.py:529 and watcher.py:79
- `get_all_beads()` -- from cli.py:124
- `update_bead(bead_id, status=None, add_labels=None, remove_labels=None)` -- wraps `bd update`
- `comment_bead(bead_id, text)` -- wraps `bd comment`

Single-caller functions (`get_bead_comments`, `_get_children`, `list_beads_by_label`) stay in their current modules and call through `bead_client` for the subprocess part if needed.

**Acceptance:** All duplicated bead operations go through `bead_client.py`. No raw `bd show`/`bd list` subprocess calls for the extracted functions remain in cli.py or watcher.py.

### Task 1.3: Unify dependency-checking logic
**Effort:** S
**Depends on:** 1.2
Three functions duplicate dependency iteration: `_waiting_on` (cli.py:194), `_has_unresolved_deps` (watcher.py:95), and `_dep_summary` (cli.py:239). Merge into one function in `bead_client.py`:
- `get_unresolved_deps(bead) -> list[str]` -- returns unresolved dep IDs (empty = all resolved)

Replace all three call sites. `_has_unresolved_deps` becomes `bool(get_unresolved_deps(bead))`. `_waiting_on` becomes `get_unresolved_deps(bead)`. `_dep_summary` calls `get_unresolved_deps` internally instead of re-implementing the iteration.

Also rename `_has_unmerged_dep_branches` (watcher.py:106) to `get_unmerged_dep_branches` since it returns a `list[str]`, not a `bool`.

**Acceptance:** `_waiting_on`, `_has_unresolved_deps`, and the duplicated logic in `_dep_summary` are eliminated. Single function used everywhere.

### Task 1.4: Fix shell injection in tmux agent spawn
**Effort:** S
In watcher.py:302-303, `bead_id` and `role` are interpolated directly into a shell command string:
```python
shell_cmd = f"{cd_prefix}export DEBUSSY_ROLE={role} DEBUSSY_BEAD={bead_id}; {claude_cmd}"
```
Use `shlex.quote()` on all interpolated values, or pass environment variables via tmux's `set-environment` instead of shell string interpolation.

**Acceptance:** No unquoted variable interpolation in shell command strings.

### Task 1.5: Deduplicate symlink cleanup in `worktree.py`
**Effort:** S
The symlink removal block (unlinking `.beads` and `.debussy` symlinks) is copy-pasted 3 times in worktree.py (lines 102-105, 200-202, 226-229). Extract to a helper:
- `_remove_symlinks(worktree_path: Path)` -- removes `.beads` and `.debussy` symlinks

**Acceptance:** Symlink cleanup logic exists in one place.

### Task 1.6: Add tests for `bead_client.py`
**Effort:** M
**Depends on:** 1.2, 1.3
Write unit tests that mock `subprocess.run`:
- Test `get_bead_json` with valid/invalid/timeout responses
- Test `get_unresolved_deps` with various dependency states
- Test `update_bead` constructs correct CLI commands

**Acceptance:** `bead_client.py` has >80% test coverage.

---

## Phase 2A: Decompose cli.py

Goal: Break cli.py into focused modules. After this phase, cli.py should be under 500 lines.

**Smoke test after completion:** `debussy status`, `debussy board`, `debussy metrics`, `debussy start`, `debussy stop` all work correctly.

### Task 2.1: Extract board rendering from cli.py into `board.py`
**Effort:** M
Move all board-related code (~200 lines) to `src/debussy/board.py`:
- `BOARD_COLUMNS`, `BOARD_INV_COLUMNS`, `BOARD_STAGE_MAP`, `DONE_LIMIT`, `STAGE_LIMIT` (cli.py:665-688)
- `_categorize_bead` (cli.py:691)
- `_build_buckets` (cli.py:702)
- `_sort_key`, `_bead_marker`, `_board_truncate` (cli.py:728-749)
- `_count_children`, `_group_done_beads`, `_render_done_content` (cli.py:752-793)
- `_render_vertical` (cli.py:796-839)
- `cmd_board` (cli.py:842)

**Acceptance:** cli.py no longer contains any board rendering code. `cmd_board` lives in `board.py`.

### Task 2.2: Extract metrics from cli.py into `metrics.py`
**Effort:** S
Move metrics code (~100 lines) to `src/debussy/metrics.py`:
- `STAGE_SHORT` (cli.py:654)
- `_fmt_duration` (cli.py:861)
- `cmd_metrics` (cli.py:869)

Break the 93-line `cmd_metrics` into smaller functions:
- `_load_events()` -- read and parse events file
- `_compute_bead_metrics(events)` -- per-bead stage trail
- `_compute_stage_averages(stage_durations)` -- aggregate stats
- `_print_metrics(bead_metrics, stage_averages)` -- display

**Acceptance:** cli.py no longer contains metrics code. No function in `metrics.py` exceeds 30 lines.

### Task 2.3: Extract tmux operations from cli.py into `tmux.py`
**Effort:** M
Move all tmux management to `src/debussy/tmux.py`:
- `_run_tmux` (cli.py:39)
- `_send_keys` (cli.py:43)
- `_create_tmux_layout` (cli.py:53)
- `_label_panes` (cli.py:70)
- `_send_conductor_prompt` (cli.py:80)
- `_stop_watcher` (cli.py:509)
- `_kill_agent` (cli.py:516)
- `_tmux_windows` (watcher.py:55) -- also used by watcher, consolidate here

**Acceptance:** Tmux subprocess calls are consolidated in `tmux.py`. Both cli.py and watcher.py import from it.

### Task 2.4: Extract status/debug display from cli.py (conditional)
**Effort:** M
**Condition:** Only proceed if cli.py exceeds 400 lines after Tasks 2.1-2.3.

Move status and debug display to `src/debussy/status.py`:
- `_print_section` (cli.py:177)
- `_print_blocked_tree` (cli.py:204)
- `_dep_summary` (cli.py:239)
- `_format_bead` (cli.py:256)
- `_get_branches` (cli.py:291)
- `_print_runtime_info` (cli.py:315)
- `_print_parent_progress` (cli.py:342)
- `cmd_status` (cli.py:367)
- `cmd_debug` (cli.py:612)

**Acceptance:** cli.py is under 400 lines. Each module has a coherent single responsibility.

---

## Phase 2B: Decompose watcher.py

Goal: Break watcher.py into focused modules. After this phase, watcher.py should be under 200 lines (the run loop and state management).

**Smoke test after completion:** `debussy watch` runs a full poll cycle, spawns agents for staged beads, transitions stages correctly on agent completion.

### Task 2.5: Extract stage transitions from watcher.py into `transitions.py`
**Effort:** S
Move `_ensure_stage_transition` and `_verify_single_stage` into `src/debussy/transitions.py` as-is, updating imports.

**Acceptance:** `_ensure_stage_transition` and `_verify_single_stage` are deleted from watcher.py and live in `transitions.py`. All call sites updated.

### Task 2.6: Decompose the 107-line transition method
**Effort:** M
**Depends on:** 2.5
Break `_ensure_stage_transition` (107 lines, 5 nesting levels) in `transitions.py` into focused functions:
- `ensure_stage_transition(bead, agent, rejections) -> TransitionResult` -- top-level dispatcher
- `_handle_in_progress_reset(bead, agent)` -- agent left bead as in_progress
- `_handle_rejection(bead, agent, rejections)` -- rejected review/test
- `_handle_acceptance_rejection(bead, agent)` -- special case: acceptance failure
- `_handle_advance(bead, agent)` -- success, advance to next stage
- `_handle_empty_branch(bead, agent, retries)` -- dev completed but no commits

Each function should be 15-25 lines max. Separate I/O (the `bd update` calls) from the decision logic -- the functions compute what labels/status to set, a single caller executes the update.

**Acceptance:** No single function in `transitions.py` exceeds 30 lines.

### Task 2.7: Add tests for stage transitions
**Effort:** M
**Depends on:** 2.6
Test the extracted transition functions:
- Agent completes successfully -> advances to next stage
- Agent rejects -> returns to development
- Agent leaves as in_progress -> resets to open
- Rejection count exceeded -> blocks bead
- Security bead routing through security-review
- Acceptance failure -> blocked for conductor
- Empty branch retry -> re-queues for development

**Acceptance:** All transition paths have test coverage.

### Task 2.8: Extract agent spawning from watcher.py into `spawner.py`
**Effort:** M
Move agent spawning code to `src/debussy/spawner.py`:
- `COMPOSERS` name list (watcher.py:40)
- `get_agent_name` (watcher.py:221)
- `spawn_agent` (watcher.py:263)
- `_spawn_tmux` (watcher.py:297)
- `_spawn_background` (watcher.py:341)
- `_create_agent_worktree` (watcher.py:240)

`AgentInfo` dataclass stays in watcher.py -- it is used throughout Watcher methods (`cleanup_finished`, `_check_timeouts`, `_remove_agent`, `_alive_agents`, `save_state`). Spawning functions return `AgentInfo` instances.

Also fix: `_spawn_background` opens a file handle (watcher.py:356) without a context manager. Ensure the handle is tracked for cleanup.

**Acceptance:** watcher.py delegates spawning to `spawner.py`. Watcher class reduced by ~200 lines.

### Task 2.9: Extract pipeline checking from watcher.py
**Effort:** M
Move pipeline scanning into `src/debussy/pipeline_checker.py`:
- `check_pipeline` (watcher.py:458) -- extract `_should_skip_bead()` from the 7 inline `continue` conditions
- `_release_ready` (watcher.py:407)
- `_reset_orphaned` (watcher.py:372)
- `_auto_close_parents` (watcher.py:707)

Break `check_pipeline`'s 75 lines into:
- `_should_skip_bead(bead_id, bead, role, state) -> str | None` -- returns skip reason or None
- `_scan_stage(stage, role, state)` -- iterates beads for one stage
- `check_pipeline(state)` -- loops over stages, delegates to `_scan_stage`

**Acceptance:** watcher.py's `run()` loop delegates to extracted modules. Watcher class under 200 lines.

---

## Phase 3: Domain Modeling

Goal: Replace magic strings with constants and co-locate related mappings. Keep it simple -- no enums, no dataclasses for pipeline data.

**Smoke test after completion:** Full `debussy watch` cycle with stage transitions; `debussy board` and `debussy metrics` display correctly.

### Task 3.1: Create stage and status string constants
**Effort:** S
Add string constants in `config.py` alongside the existing `STAGE_TO_ROLE` and `NEXT_STAGE` dicts:
```python
STAGE_DEVELOPMENT = "stage:development"
STAGE_REVIEWING = "stage:reviewing"
STAGE_SECURITY_REVIEW = "stage:security-review"
STAGE_MERGING = "stage:merging"
STAGE_ACCEPTANCE = "stage:acceptance"
STAGE_INVESTIGATING = "stage:investigating"
STAGE_CONSOLIDATING = "stage:consolidating"

STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_CLOSED = "closed"
STATUS_BLOCKED = "blocked"
```

Replace the 50+ magic string occurrences across the codebase with these constants.

**Acceptance:** No raw stage/status strings remain in Python code (except at the CLI boundary in `bead_client.py` where constants are used to construct commands).

### Task 3.2: Normalize prompt builder error handling
**Effort:** S
The fallback prompt in `prompts/__init__.py:39-45` silently produces a vague prompt for unknown roles. Add a `ValueError` for unknown roles instead.

Keep the existing lambda wrappers -- they clearly communicate which builders need which args and are only 3 lines.

**Acceptance:** Unknown roles raise `ValueError`. Existing lambda wrappers remain.

### Task 3.3: Co-locate stage mapping dictionaries
**Effort:** S
**Depends on:** 3.1
Five separate stage mapping dicts exist across two files:
1. `STAGE_TO_ROLE` (config.py:25)
2. `NEXT_STAGE` (config.py:35)
3. `STAGE_SHORT` (cli.py:654 / metrics.py after extraction)
4. `BOARD_STAGE_MAP` (cli.py:678 / board.py after extraction)
5. `BOARD_COLUMNS` (cli.py:665 / board.py after extraction)

Co-locate the core pipeline dicts (`STAGE_TO_ROLE`, `NEXT_STAGE`, `STAGE_SHORT`) in `config.py`. The board-specific display dicts (`BOARD_STAGE_MAP`, `BOARD_COLUMNS`) stay in `board.py` but reference the constants from Task 3.1. Security routing (the special case where `stage:reviewing` goes to `stage:security-review` instead of `stage:merging`) should be encoded as data in `NEXT_STAGE`, not as an `if "security" in labels` check buried in transition logic.

**Acceptance:** Core stage configuration is defined in one place. Adding a new stage means updating one location for pipeline behavior.

---

## Phase 4: Quality Infrastructure

Goal: Add type safety to critical modules, clean up error handling.

**Smoke test after completion:** Full end-to-end cycle -- `debussy start`, create a bead with `stage:development`, verify it progresses through the pipeline.

### Task 4.1: Add type hints to `bead_client.py` and `transitions.py`
**Effort:** S
Add return types and parameter types to all public and module-level functions in `bead_client.py` and `transitions.py` -- the two modules where type errors could cause real bugs (incorrect CLI commands, wrong stage transitions).

**Acceptance:** `mypy` passes on `bead_client.py` and `transitions.py` (no `--strict` flag).

### Task 4.2: Audit and fix bare `except Exception: pass` patterns
**Effort:** M
30+ instances of `except Exception: pass` silently swallow errors. For each instance:
- If the error is expected and ignorable (e.g., cleanup of already-deleted resource), add a specific exception type
- If the error should be logged, log it at debug/warning level
- If the error should propagate, remove the try/except

This is a codebase-wide sweep, done after Phase 2 when smaller files make it easier to audit.

**Acceptance:** No bare `except Exception: pass` remains. Each exception handler either catches a specific type, logs the error, or has a code comment explaining why it is intentionally ignored.

---

## Dependency Graph

```
Phase 1 (Foundation)
  1.1 is independent (do first -- trivial, no deps)
  1.2 → 1.3
  1.4, 1.5 are independent
  1.6 depends on 1.2, 1.3 (test bead_client right after creating it)

Phase 2A (Decompose cli.py) -- depends on Phase 1
  2.1, 2.2, 2.3 are independent
  2.4 is conditional on cli.py size after 2.1-2.3

Phase 2B (Decompose watcher.py) -- depends on Phase 1; independent of 2A
  2.5 → 2.6 → 2.7
  2.8, 2.9 are independent of each other but each modifies watcher.py
  2.7 depends on 2.6 (test transitions right after decomposing)

Phase 3 (Domain) -- depends on Phase 1; easier after Phase 2
  3.1 → 3.3
  3.2 is independent

Phase 4 (Quality) -- depends on Phases 1-2
  4.1 depends on Phase 2
  4.2 depends on Phase 2 (easier with smaller files)
```

---

## Risk Considerations

1. **Circular imports** -- Extracting modules creates import dependencies. Keep the dependency graph one-directional: `cli/watcher -> board/metrics/status/transitions/spawner/pipeline_checker -> bead_client -> config`. Never import upward.

2. **Breaking the watcher in production** -- The watcher is a long-running process managing real agents. Run a smoke test after each phase: `debussy watch` for 60 seconds without crashes, `debussy status` prints output. Keep each task's diff small enough to revert cleanly.

3. **State file compatibility** -- `watcher_state.json` is read by both cli.py (via `_get_running_agents`) and watcher.py. If the serialization format changes, ensure backward compatibility or migrate atomically. Note: `_get_running_agents` (cli.py:145) reads watcher_state.json directly and will break if state shape changes.

4. **Subprocess boundary** -- The `bd` CLI is the boundary between debussy and the beads system. `bead_client.py` should be a thin wrapper, not an ORM. Don't over-abstract.

5. **Silent error regression** -- When fixing `except Exception: pass` (Task 4.2), be careful not to surface errors that were intentionally suppressed (e.g., cleanup of already-deleted resources). Test each change individually.

6. **Stage mapping refactor risk** -- Co-locating stage dicts (Task 3.3) touches display code in board.py and metrics.py. Do this after Phase 2 when the files are smaller and changes are more isolated.

7. **Scope creep** -- Each task should change one thing. Don't "improve" adjacent code during a refactoring task. If you find a bug, file a separate bead.

8. **Smoke tests between phases** -- Unit tests mock subprocess.run, but the real risk is that import paths break or argument passing changes. A smoke test after each phase (`debussy watch` runs for 60 seconds, `debussy status` prints output) catches most regressions and costs almost nothing.

9. **AgentInfo coupling** -- `AgentInfo` is used throughout Watcher methods (`cleanup_finished`, `_check_timeouts`, `_remove_agent`, `_alive_agents`, `save_state`). It stays in watcher.py. Spawner functions return `AgentInfo` instances to avoid tight import coupling.

## Principles

- **Simplicity first** -- Extract, don't abstract. Moving code to a new file is not the same as wrapping it in a framework. Use string constants, not enums. Use co-located dicts, not dataclasses. Use raw dicts for bead data, not typed wrappers.
- **Surgical changes** -- Each task changes one thing. Match existing style in unchanged code.
- **No new features** -- This is pure refactoring. Behavior must be identical before and after.
- **Small files, small functions** -- Target: no file over 300 lines, no function over 30 lines.
- **Test at boundaries** -- Focus tests on bead_client and transition logic, not internal helpers.
- **Smoke test between phases** -- Run `debussy watch` and `debussy status` after each phase to catch import and argument regressions.
