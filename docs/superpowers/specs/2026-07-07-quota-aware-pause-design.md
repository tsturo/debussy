# Quota-Aware Pipeline Pause & Auto-Resume

Date: 2026-07-07
Status: Draft

## Context

Agents run as `claude` CLI subprocesses (background processes or tmux windows) spawned by
the watcher. The conductor pane and every worker agent draw from the **same account quota**
(the subscription's 5-hour session limit and weekly limit). When that quota is exhausted,
every `claude` invocation fails — including the conductor's, so it can no longer report
status, make decisions, or resume supervising.

Today there is no awareness of quota. The pipeline keeps spawning agents that immediately
die at the wall, thrashing until `MAX_RETRIES` worth of failures accrue, and the run
effectively stalls with no recovery path until a human intervenes.

The watcher is well-positioned to fix this: it is a persistent 5s poll loop
(`watcher.py:357`), it already gates all spawning on a `paused` config flag
(`watcher.py:365`), it already reads each dead agent's log tail (`diagnostics.read_log_tail`),
and on agent death it already resets the task to pending (`watcher.py:189`), removes the
worktree (`_remove_agent`), and deletes the developer branch (`delete_task_branch`,
`watcher.py:250`).

## Goals

1. **Proactively** pause the worker pipeline *before* the account quota is fully drained,
   reserving headroom so the conductor stays functional.
2. Detect exhaustion via `ccusage` (parses local `~/.claude` transcripts) run before the
   spawn phase.
3. Record the reset time and **auto-resume** the pipeline once quota is restored, verifying
   before resuming so it does not immediately re-hit the wall.
4. Cover both the requested windows: the 5-hour **session** limit (proactively) and the
   **weekly** limit (via the reactive backstop, below).
5. Keep the feature opt-in and off by default, so existing users are unaffected and
   `ccusage` is only required when enabled.

## Non-Goals

- **Conductor auto-restart.** The conductor is an interactive pane; when the account is
  capped it is also limited. This feature governs the *worker pipeline*. The conductor
  reserve exists so a human-driven or already-running conductor can still act; we do not
  respawn it.
- **A guaranteed-accurate quota ceiling.** Anthropic does not publish the limit; `ccusage`
  estimates it from your highest historical block. The margin is configurable and the
  reactive backstop covers estimate misses.
- **Multi-account / API-key fallback.**

## Two layers, two distinct goals

The design has two detection layers that feed **one** pause+resume mechanism. They serve
*different* goals — keeping this straight matters:

- **Proactive (ccusage)** — the primary defense, and the **only** layer that protects the
  conductor reserve, because it fires *before* the wall (at 97% of the estimated session
  ceiling). It cleanly catches the 5-hour session limit and yields an accurate reset time
  (block end).
- **Reactive backstop (log parsing)** — fires *after* an agent hits the wall, so by then the
  account is already drained and it does **not** protect the reserve. Its job is different:
  (a) cover the **weekly** limit, which ccusage cannot reliably see; (b) recover gracefully
  when the proactive estimate misses or ccusage is unavailable — turning a thrash-until-
  MAX_RETRIES stall into a clean pause with the authoritative reset timestamp from the
  server's message, so auto-resume fires at the right time.

A quota-pause is deliberately **"manual `debussy pause` + a resume timer"**: it kills
in-flight workers, resets their tasks to pending, and removes their worktrees/branches —
using the watcher primitives already exercised on agent death — plus it records
`pause_reason=quota` and `paused_until` so the watcher auto-resumes. Killing in-flight
workers is what makes the 97% reserve real: stopping only new spawns would let up to
`max_total_agents` running agents burn through the remaining headroom and starve the
conductor anyway.

## Design

### 1. New module `src/debussy/quota.py`

Isolates all `ccusage` coupling and log-signal parsing behind a small interface so the
watcher never touches ccusage's JSON shape. Internal tuning values are module constants,
matching house style (`AGENT_TIMEOUT`, `POLL_INTERVAL`, `LOG_TAIL_LINES`):

```python
QUOTA_CHECK_INTERVAL = 60      # min seconds between ccusage calls while running
QUOTA_DEFAULT_COOLDOWN = 3600  # fallback wait when a reset ts can't be parsed
QUOTA_TIMEOUT = 15             # ccusage subprocess timeout

@dataclass
class QuotaStatus:
    exhausted: bool
    reset_at: float | None   # unix ts of window reset; None if unknown
    used: int                # diagnostic, for the pause log line
    limit: int               # diagnostic, for the pause log line
```

- `check_quota(command: str, margin: float) -> QuotaStatus | None`
  - Runs `command` (shlex-split) with `QUOTA_TIMEOUT`, capturing stdout.
  - Parses the active block: `used` = block total tokens, `limit` = the ceiling reported
    under `--token-limit max`, `exhausted = used >= margin * limit`, `reset_at` = the active
    block's end time parsed to a unix ts.
  - Returns `None` on **any** failure — tool missing, non-zero exit, timeout, empty/invalid
    JSON, no active block, `limit <= 0`, a malformed `margin`, or any other exception (the
    whole body is exception-safe). `None` means "cannot determine" and callers **fail
    open** — a broken monitor must never brick the pipeline.
- `detect_limit_signal(log_tail: str, now: float) -> float | None`
  - The reactive backstop. Matches the CLI's usage-limit message. If it carries a reset
    unix ts, returns it; if the message matches but has no parseable ts, returns
    `now + QUOTA_DEFAULT_COOLDOWN`; if no match, returns `None`.

Single-responsibility helpers (`_parse_active_block`, `_extract_reset_ts`) keep each
function small and independently testable.

### 2. Watcher integration (`src/debussy/watcher.py`)

New `__init__` fields: `self._last_quota_check = 0.0` (time of last ccusage call) and
`self._quota_warned = 0.0` (rate-limits fail-open warnings). No instance flag is needed for
the backstop — see §3.

New methods (each small, single purpose):

- `_quota_gate() -> QuotaStatus | None` — returns a status only when a *fresh* check says
  exhausted:
  ```
  cfg = get_config()
  if not cfg.get("quota_check"): return None
  now = time.time()
  if now - self._last_quota_check < QUOTA_CHECK_INTERVAL: return None
  self._last_quota_check = now
  status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
  if status is None:      # fail open; warn at most once per interval
      self._warn_quota_unavailable(now)
      return None
  return status if status.exhausted else None
  ```
- `_pause_running_agents(comment: str)` — reuses the exact primitives the death path already
  uses: for each agent in `list(self.running.items())`, `agent.stop()`, then
  `add_comment(db, task, ...)` + `release_task(db, task)` (active→pending), then
  `_remove_agent(key, agent)` (removes the worktree), and `delete_task_branch(agent.task)`
  for developer roles. No branch *scan* — the task ids are known, and `create_worktree`
  self-heals a leftover branch on respawn regardless (`worktree.py:94-108`).
- `_enter_quota_pause(reset_at: float | None, source: str, status=None)` — logs
  (used/limit/computed pct/reset, and `source` = `"quota"` or `"wall-hit"` for the log line
  only), calls `_pause_running_agents("Paused: quota limit reached")`, then sets config
  `paused=True`, `pause_reason="quota"`, `paused_until = reset_at or time.time() +
  QUOTA_DEFAULT_COOLDOWN`. Notifies the conductor when `notify_conductor` is on.
- `_maybe_auto_resume()`:
  ```
  cfg = get_config()
  if not cfg.get("paused") or cfg.get("pause_reason") != "quota": return
  if not cfg.get("quota_check"):        # feature disabled while paused -> release
      self._clear_quota_pause(); return
  until = cfg.get("paused_until")
  if until is None or time.time() < until: return
  status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))  # always on resume
  if status is None:                    # unverifiable -> fail open, resume
      self._clear_quota_pause(); return
  if status.exhausted:                  # still capped -> extend
      set_config("paused_until", status.reset_at or time.time() + QUOTA_DEFAULT_COOLDOWN)
  else:
      self._last_quota_check = time.time()   # avoid an immediate redundant re-check
      self._clear_quota_pause()
  ```
- `_clear_quota_pause()` — sets `paused=False`, `pause_reason=None`, `paused_until=None`.

Loop wiring in `run()` (order matters):

```
_refresh_tmux_cache()
_check_timeouts()
pending = cleanup_finished()   # now RETURNS an optional backstop reset-ts (§3)
_kill_orphan_windows()
reset_orphaned(self)

if pending is not None:                     # consume backstop after the cleanup loop
    self._enter_quota_pause(pending, "wall-hit")

_maybe_auto_resume()
if not get_config().get("paused", False):
    _refresh_tmux_cache()
    status = self._quota_gate()
    if status is not None:
        self._enter_quota_pause(status.reset_at, "quota", status)
    else:
        release_ready(self)
        check_pipeline(self)
```

`_last_quota_check` gates ccusage to at most once per `QUOTA_CHECK_INTERVAL` while running;
while quota-paused, ccusage is only invoked at/after `paused_until`.

### 3. Reactive backstop hook (`cleanup_finished`)

`cleanup_finished` currently returns nothing. Change it to return the earliest backstop
reset-ts seen this tick (or `None`). In the existing agent-death branch, after
`read_log_tail`, call `detect_limit_signal(log_tail, now)`; track the minimum non-None
result across the loop and return it. The kill is **not** done inline — that path already
iterates a `list(self.running.items())` copy and calls `del self.running[key]` via
`_remove_agent`, so entering a pause that also removes agents mid-loop risks a
double-removal `KeyError`. Returning the ts and letting `run()` call `_enter_quota_pause`
after the loop avoids that. This reuses log reading already happening on death and adds no
new spawn-path cost.

**Failure-count rollback.** The death branch increments `self.failures[task]`
(`watcher.py:239`) *before* it reads the log tail. A quota wall-hit is a stall, not a task
defect, so when `detect_limit_signal` matches for a dead agent the increment must be rolled
back for that task (`self.failures[task] = max(0, self.failures.get(task, 0) - 1)`, or pop
it). Otherwise repeated quota cycles — especially the weekly limit — erode the retry budget
and eventually park a healthy task at `MAX_RETRIES`. The task is already reset to pending by
the existing death path (`release_task`, `watcher.py:244`), so on resume it respawns
cleanly with its retry budget intact.

### 4. Shared pause marker only (`src/debussy/cli.py`)

No module extraction (the watcher reuses its own primitives, §2). The only CLI changes are
the pause-state markers so auto-resume never fires on a manual pause:

- `cmd_pause` — set `pause_reason="manual"` and clear `paused_until`.
- `cmd_resume` — clear `pause_reason` and `paused_until` alongside `paused=False`.
- `cmd_start` — clear `pause_reason`/`paused_until` on a fresh start.

Its existing kill path (`_kill_all_agents`, which works off the state file) is unchanged.

### 5. Configuration (`src/debussy/config.py`)

New `DEFAULTS` (all opt-in; feature is a no-op when `quota_check` is false, and ccusage is
not required in that case):

| key | default | meaning |
|-----|---------|---------|
| `quota_check` | `false` | master switch |
| `quota_command` | `"ccusage blocks --active --json --token-limit max"` | ccusage invocation (shlex-split) |
| `quota_margin` | `0.97` | pause when `used >= margin * limit` |

`KNOWN_KEYS` gains: `quota_check`, `quota_command`, `quota_margin`, `pause_reason`,
`paused_until` (the last two are runtime pause state, added — like the existing `paused` —
so `clean_config` does not strip them). Check-interval and cooldown are constants in
`quota.py`, not config (§1).

No new subcommands; configuration is via the existing `debussy config <key> <value>`.

### 6. Prerequisite & documentation

`ccusage` must be installed when `quota_check` is enabled (e.g. `npm i -g ccusage`).
Implementation includes documenting the toggle and prerequisite in `CLAUDE.md`'s command
list; enabling without ccusage present fails open (pipeline runs, warning logged, reactive
backstop still active).

## Edge Cases

- **ccusage missing / errors / timeout / bad JSON** → `check_quota` returns `None` → fail
  open. Pipeline runs; the reactive backstop still catches real wall-hits. Fail-open
  warnings are rate-limited to once per `QUOTA_CHECK_INTERVAL`.
- **Reset ts unparseable** (proactive or reactive) → `paused_until = now +
  QUOTA_DEFAULT_COOLDOWN`, so auto-resume still eventually fires (never stuck forever).
- **Watcher restart with `paused_until` in the past** → `_last_quota_check` resets to 0 and
  `_maybe_auto_resume` re-checks on the first tick, clearing or extending accordingly.
- **Manual pause while quota-paused** → `cmd_pause` sets `pause_reason="manual"`;
  auto-resume no longer fires; the pipeline waits for a manual `debussy resume`.
- **Manual resume while still over quota** → state cleared; the next `_quota_gate` (after
  the interval) re-pauses with an explanatory log. A force-override is out of scope (YAGNI).
- **`quota_check` disabled while quota-paused** → `_maybe_auto_resume` releases the pause
  immediately rather than holding it on a disabled feature.
- **Multiple agents dying in one tick, each matching the signal** → `cleanup_finished`
  returns the earliest reset-ts; a single `_enter_quota_pause` fires (it kills all remaining
  agents anyway).
- **`get_config` mtime cache** (`config.py:144`) → after `set_config`, `atomic_write`
  replaces the file with a fresh mtime, so the next `get_config` reloads. On macOS/APFS
  (nanosecond mtime) intra-tick re-reads are always fresh. Worst case on a coarse (1s) mtime
  filesystem is a one-tick (~5s) delay before a just-cleared pause is observed — a delay,
  not a correctness bug.

## To Verify During Implementation

These are asserted-by-inspection and must be confirmed against real output, not hardcoded
on assumption:

1. The exact JSON field names of `ccusage blocks --active --json --token-limit max`
   (active-block token total, the `--token-limit max` ceiling, and the block end time).
2. The exact format of the `claude` CLI usage-limit message in background/`--print` mode,
   and whether it embeds a reset unix ts — this drives the `detect_limit_signal` regex and,
   with it, the reliability of **weekly** coverage. If the message proves unusable, weekly
   coverage degrades and that limitation must be surfaced, not hidden.

## Testing

Per repo test layout (`tests/test_<module>.py`; note `test_watcher.py` is net-new — the
watcher currently has no tests, so tmux/subprocess/db will need stubbing):

- `tests/test_quota.py`
  - `check_quota`: sample JSON below margin → not exhausted; above margin → exhausted;
    `reset_at` parsed from block end.
  - `check_quota` fail-open: non-zero exit, timeout, invalid/empty JSON, no active block,
    `limit <= 0` → all return `None` (subprocess monkeypatched).
  - `detect_limit_signal`: wall-hit line with a reset ts → that ts; matching line without a
    ts → `now + QUOTA_DEFAULT_COOLDOWN`; unrelated log → `None`.
- `tests/test_watcher.py` (with `check_quota`/`detect_limit_signal` stubbed)
  - Gate exhausted → `_enter_quota_pause` sets `paused`/`pause_reason`/`paused_until`,
    `_pause_running_agents` stops agents and resets tasks, and no spawn occurs.
  - `_maybe_auto_resume`: `now < until` → no-op; `now >= until` and quota back → cleared;
    `now >= until` and still capped → `paused_until` extended; `pause_reason="manual"` →
    no-op; feature disabled while quota-paused → cleared.
  - Backstop: `cleanup_finished` returns the reset-ts when a dead agent's log tail matches;
    the loop then enters the quota-pause.
  - Backstop failure rollback: a quota-signal death does not leave `self.failures[task]`
    incremented (retry budget preserved across quota cycles).
- `tests/test_config.py`: new defaults present; `KNOWN_KEYS` includes the new keys;
  `clean_config` preserves `pause_reason`/`paused_until`.
