# Conductor Autonomy: Supervision Loop, Autonomy Modes, Per-Role Model/Effort

Date: 2026-07-02
Status: Approved

## Context

The pipeline should run until all tasks are done without manual shepherding. Today the user
repeats the same instruction every session: "monitor and fix all pipeline issues, make
decisions; if you can't decide, spawn investigation subagents, review their findings, pick
the recommended solution." The conductor prompt has a monitoring section but stops at
"diagnose via logs and act" — no decision protocol, no investigation delegation, no policy
for giving up.

Additionally:

- `YOLO_MODE` (config.py) exists but only controls `--dangerously-skip-permissions`.
  Decision autonomy is a separate axis with no configuration.
- `role_models` defaults reference `claude-opus-4-6[1m]` / `claude-sonnet-4-6[1m]`, two
  generations old. There is no per-role effort configuration; the CLI supports
  `--effort <level>`.

## Goals

1. Bake the supervision/decision protocol into the shipped conductor prompt.
2. Add an autonomy mode: `auto` (default, never asks mid-run) and `manual` (asks at
   decision points).
3. Refresh model defaults to current models and add per-role effort.

## Non-Goals

- No `--manual`/`--auto` flags on `debussy start` (the config key covers it).
- No new watcher logic.
- `YOLO_MODE` (permissions) is untouched and unrelated.

## Revisions after multi-perspective review (2026-07-02)

The initial design parked tasks via `takt block`. Review against the watcher code showed
`release_ready` auto-unblocks any blocked task whose dependencies are resolved, so a
conductor park would be resurrected on the next tick. Parking is now a dedicated `parked`
stage (takt schema v5 widens the stage CHECK constraint): the watcher never scans it,
dependency resolution never satisfies it, and the board shows it as its own column.
`release_ready` also no longer unblocks tasks at MAX_REJECTIONS, closing a pre-existing
churn loop. Additionally: `get_config()` deep-merges dict-valued keys (partial
`role_models` overrides no longer wipe other roles' defaults), `role_cli_args` only emits
flags for the claude provider, and the conductor prompt gained a terminal check,
mode-scoped decision bullets, persisted ladder counts, and an acceptance-task carve-out.

## Design

### 1. Conductor supervision loop (`src/debussy/prompts/conductor.md`)

Replace the current `PIPELINE MONITORING (automatic)` and `MONITORING REJECTION LOOPS`
sections with a single `PIPELINE SUPERVISION` section containing:

**Monitoring mechanism** (unchanged): after releasing tasks, run
`sleep MONITOR_INTERVAL && debussy board` in the background; on each wake, compare board
state; diagnose changes.

**Diagnosis sources**: `.debussy/logs/<agent-name>.log`, `.debussy/logs/watcher.log`,
`takt show <id>`, `takt log <id>`.

**Decision protocol**: decide yourself — do not defer. When information is missing, spawn
one or more investigation subagents (Task tool), each with a single specific question
(e.g. "why does test X fail on branch Y — root cause only, no fixes"). Evaluate the
findings, choose the recommended solution, act on it.

**Escalation ladder** (per failing task):

1. Rejected 2× → read reviewer comments, rewrite the description, split the task, or add
   implementation hints (absorbs the existing rejection-loop guidance).
2. Still failing → spawn an investigation subagent for root cause (bad spec, missing
   dependency, environment issue); re-plan: new task breakdown, different approach, or
   restructured deps.
3. After 2 failed re-plans → the task is not deliverable as specified. Park it
   (`takt advance <id> --to parked` — see Revisions section). Dependents stay parked
   automatically. Keep driving all independent tasks to done.
4. End of run → final report: what shipped, what was parked and why, what the parked
   tasks blocked.

**Mode placeholder**: an `AUTONOMY_INSTRUCTIONS` placeholder line inside this section,
replaced at prompt-build time (section 2).

### 2. Autonomy mode

**Config** (`src/debussy/config.py`):

- `DEFAULTS["autonomy"] = "auto"`.
- Add `"autonomy"` to `KNOWN_KEYS`.
- Any value other than `"manual"` is treated as `auto`.

**Prompt injection** (`src/debussy/prompts/__init__.py`): alongside the existing
`MONITOR_INTERVAL` substitution, replace `AUTONOMY_INSTRUCTIONS` with mode-specific text:

- `auto`: Never ask the user mid-run. Make every recovery and re-planning decision
  yourself. Log each decision (what, why, alternatives considered) to
  `.debussy/conductor-context.md`. When all tasks are done or parked, produce the final
  report.
- `manual`: At each decision point (rejection loop, stuck agent, re-plan, parking),
  present the options with your recommendation and wait for the user's choice.

**Usage**: `debussy config autonomy manual` (existing config command, no CLI changes).

### 3. Models and effort per role

**New `role_models` defaults** (`src/debussy/config.py`, plain IDs):

| Role | Model | Effort |
|------|-------|--------|
| conductor | `claude-fable-5` | high |
| developer | `claude-sonnet-5` | medium |
| reviewer | `claude-opus-4-8` | high |
| security-reviewer | `claude-fable-5` | high |
| integrator | `claude-sonnet-5` | low |
| tester | `claude-sonnet-5` | low |

Rationale: capability at the decision points (conductor, reviews); cost control at the
parallel bottleneck (up to 10 developers).

**New `role_efforts` default** in `DEFAULTS` with the effort column above; add
`"role_efforts"` to `KNOWN_KEYS`.

**Touchpoints** — pass `--effort <level>` when set for the role, following the same
append-when-set pattern as `--model`:

- `src/debussy/tmux.py:_build_conductor_cmd` (conductor)
- `src/debussy/spawner.py:_spawn_tmux` (role agents, tmux windows)
- `src/debussy/spawner.py:_spawn_background` (role agents, background processes)

**Verification item during implementation**: whether the `[1m]` context-window suffix is
accepted for the new model IDs (`claude --model 'claude-sonnet-5[1m]'`). If unsupported
or unverifiable, ship plain IDs.

## Edge Cases

- `get_config()` deep-merges dict-valued keys against DEFAULTS (revised after review):
  a partial `role_models` override customizes only the listed roles; unlisted roles get
  current defaults. Per-role opt-out: set the role's value to `""`.
- `role_efforts` missing a role → no `--effort` flag for that role (CLI session default
  applies).
- Unknown `autonomy` value → behaves as `auto`.
- A parked task with no dependents simply appears in the final report; the batch
  acceptance task depending on it stays parked, so acceptance never runs on an incomplete
  batch silently.

## Testing

Per repo convention (one test module per source module):

- `tests/test_config.py`: new defaults (`autonomy`, `role_efforts`, updated
  `role_models`); `KNOWN_KEYS` includes the new keys.
- `tests/test_prompts.py`: `AUTONOMY_INSTRUCTIONS` is substituted for both modes; no
  placeholder text remains in the built prompt; supervision-ladder text present.
- `tests/test_spawner.py`: `--effort` appears in tmux and background spawn commands when
  configured for the role; absent when not configured.
- `tests/test_tmux.py`: conductor command includes `--model` and `--effort` from config.
