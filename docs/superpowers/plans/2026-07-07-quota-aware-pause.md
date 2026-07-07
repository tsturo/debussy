# Quota-Aware Pipeline Pause & Auto-Resume — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pause the worker pipeline before the account quota is drained (reserving conductor headroom) and auto-resume once it resets.

**Architecture:** A new `quota.py` isolates all ccusage/log parsing behind a tiny interface. The watcher proactively checks ccusage before spawning; at ≥97% of the estimated ceiling it kills in-flight workers, resets their tasks, and records `pause_reason=quota`/`paused_until`. A persistent loop auto-resumes at reset after re-verifying. A reactive log-signal backstop covers the weekly limit and ccusage misses.

**Tech Stack:** Python ≥3.10 (stdlib only — `subprocess`, `json`, `shlex`, `re`, `datetime`), pytest, ccusage (external CLI, opt-in).

**Design doc:** `docs/superpowers/specs/2026-07-07-quota-aware-pause-design.md`

## Global Constraints

- **Python floor: 3.10.** No 3.11+ only APIs. Parse ISO timestamps via `datetime.fromisoformat(s.replace("Z", "+00:00"))`, not bare `Z` handling.
- **Feature is opt-in:** `quota_check` defaults to `false`; when false the watcher behavior is unchanged and ccusage is never invoked.
- **Fail open:** any ccusage failure (missing tool, non-zero exit, timeout, bad JSON, malformed margin, no active block, `limit <= 0`) → return `None` → pipeline proceeds. A broken monitor must never halt the pipeline.
- **No comments added** to source (repo/user convention). Docstrings are fine where the module already uses them.
- **Stage files by name** in every commit — never `git add .`/`-A`.
- **Every commit message ends with these two trailer lines:**
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_017RxUqNak7Af2vaS5A6TwtY
  ```
- **Verified ccusage schema** (`ccusage blocks --active --json --token-limit max`): `{"blocks":[{"isActive":true,"endTime":"2026-07-07T11:00:00.000Z","totalTokens":30488744,"tokenLimitStatus":{"limit":242987870}}]}`. Use `totalTokens` as `used`, `tokenLimitStatus.limit` as `limit`, `endTime` as the reset. Ignore `percentUsed` (it is projection-based, not current usage).
- **Verified CLI limit phrases:** `"usage limit reached"`, `"limit reached"` (covers "5-hour limit reached", "weekly limit reached"), `"hit your limit"`. An optional embedded `|<unix_ts>` may follow "limit reached".

---

### Task 1: `quota.py` — ccusage query (`check_quota`)

**Files:**
- Create: `src/debussy/quota.py`
- Test: `tests/test_quota.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `QUOTA_CHECK_INTERVAL = 60`, `QUOTA_DEFAULT_COOLDOWN = 3600`, `QUOTA_TIMEOUT = 15` (module constants).
  - `@dataclass QuotaStatus(exhausted: bool, reset_at: float | None, used: int, limit: int)`
  - `check_quota(command: str, margin: float) -> QuotaStatus | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quota.py`:

```python
"""Tests for the quota detection layer (ccusage + limit-signal parsing)."""

import json
import subprocess

import pytest

from debussy import quota
from debussy.quota import QuotaStatus, check_quota

ACTIVE_BLOCK = {
    "blocks": [
        {
            "id": "2026-07-07T06:00:00.000Z",
            "isActive": True,
            "endTime": "2026-07-07T11:00:00.000Z",
            "totalTokens": 100,
            "tokenLimitStatus": {"limit": 1000},
        }
    ]
}


def _fake_run(stdout="", returncode=0, raises=None):
    def runner(*args, **kwargs):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return runner


def test_check_quota_below_margin_not_exhausted(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    status = check_quota("ccusage blocks --active --json --token-limit max", 0.97)
    assert status is not None
    assert status.used == 100
    assert status.limit == 1000
    assert status.exhausted is False


def test_check_quota_at_or_above_margin_exhausted(monkeypatch):
    data = json.loads(json.dumps(ACTIVE_BLOCK))
    data["blocks"][0]["totalTokens"] = 970
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(data)))
    status = check_quota("cmd", 0.97)
    assert status.exhausted is True


def test_check_quota_reset_at_parsed_from_endtime(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    status = check_quota("cmd", 0.97)
    # 2026-07-07T11:00:00Z == 1783594800 unix seconds
    assert status.reset_at == pytest.approx(1783594800.0)


@pytest.mark.parametrize("kwargs", [
    {"returncode": 1, "stdout": ""},
    {"stdout": "not json"},
    {"stdout": ""},
    {"stdout": json.dumps({"blocks": []})},
    {"stdout": json.dumps({"blocks": [{"isActive": True, "totalTokens": 5,
                                       "tokenLimitStatus": {"limit": 0}}]})},
])
def test_check_quota_fails_open_to_none(monkeypatch, kwargs):
    monkeypatch.setattr(subprocess, "run", _fake_run(**kwargs))
    assert check_quota("cmd", 0.97) is None


def test_check_quota_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        _fake_run(raises=subprocess.TimeoutExpired("cmd", 15)))
    assert check_quota("cmd", 0.97) is None


def test_check_quota_malformed_margin_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    assert check_quota("cmd", "not-a-number") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quota.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'debussy.quota'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/debussy/quota.py`:

```python
"""Quota detection: ccusage queries and usage-limit log-signal parsing."""

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime

QUOTA_CHECK_INTERVAL = 60
QUOTA_DEFAULT_COOLDOWN = 3600
QUOTA_TIMEOUT = 15


@dataclass
class QuotaStatus:
    exhausted: bool
    reset_at: float | None
    used: int
    limit: int


def _parse_iso(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _active_block(data: dict) -> dict | None:
    for block in data.get("blocks", []):
        if block.get("isActive"):
            return block
    return None


def check_quota(command: str, margin: float) -> QuotaStatus | None:
    try:
        result = subprocess.run(
            shlex.split(command), capture_output=True, text=True, timeout=QUOTA_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        block = _active_block(json.loads(result.stdout))
        if block is None:
            return None
        used = int(block.get("totalTokens", 0))
        limit = int(block.get("tokenLimitStatus", {}).get("limit", 0))
        if limit <= 0:
            return None
        return QuotaStatus(
            exhausted=used >= margin * limit,
            reset_at=_parse_iso(block.get("endTime")),
            used=used,
            limit=limit,
        )
    except (subprocess.SubprocessError, OSError, ValueError, TypeError, KeyError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quota.py -v`
Expected: PASS (all 9+ cases).

- [ ] **Step 5: Commit**

```bash
git add src/debussy/quota.py tests/test_quota.py
git commit  # subject: "Add quota.py check_quota (ccusage active-block gate)"  + trailers
```

---

### Task 2: `quota.py` — usage-limit log signal (`detect_limit_signal`)

**Files:**
- Modify: `src/debussy/quota.py`
- Test: `tests/test_quota.py`

**Interfaces:**
- Consumes: (own module).
- Produces: `detect_limit_signal(log_tail: str) -> tuple[bool, float | None]` — `(hit, reset_at)`. `hit` is True when a usage-limit message is present; `reset_at` is the embedded unix ts if the message carries a `|<ts>` form, else `None` (caller resolves the time).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_quota.py`:

```python
from debussy.quota import detect_limit_signal


def test_detect_signal_human_message_hit_no_ts():
    tail = "Claude usage limit reached. Your limit will reset at 2pm (America/New_York)"
    hit, reset_at = detect_limit_signal(tail)
    assert hit is True
    assert reset_at is None


def test_detect_signal_five_hour_phrase():
    hit, _ = detect_limit_signal("5-hour limit reached ∙ resets 3pm")
    assert hit is True


def test_detect_signal_pipe_timestamp_seconds():
    hit, reset_at = detect_limit_signal("Claude AI usage limit reached|1783594800")
    assert hit is True
    assert reset_at == pytest.approx(1783594800.0)


def test_detect_signal_pipe_timestamp_millis():
    hit, reset_at = detect_limit_signal("usage limit reached|1783594800000")
    assert hit is True
    assert reset_at == pytest.approx(1783594800.0)


def test_detect_signal_no_match():
    hit, reset_at = detect_limit_signal("normal agent output, all good\ndone.")
    assert hit is False
    assert reset_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quota.py -k detect_signal -v`
Expected: FAIL — `ImportError: cannot import name 'detect_limit_signal'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/debussy/quota.py`:

```python
LIMIT_PHRASES = ("usage limit reached", "limit reached", "hit your limit")
_PIPE_TS = re.compile(r"limit reached\s*\|\s*(\d{10,13})", re.IGNORECASE)


def detect_limit_signal(log_tail: str) -> tuple[bool, float | None]:
    lowered = log_tail.lower()
    if not any(phrase in lowered for phrase in LIMIT_PHRASES):
        return False, None
    match = _PIPE_TS.search(log_tail)
    if not match:
        return True, None
    raw = int(match.group(1))
    return True, (raw / 1000.0 if raw >= 1_000_000_000_000 else float(raw))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quota.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/quota.py tests/test_quota.py
git commit  # subject: "Add detect_limit_signal for usage-limit log backstop"  + trailers
```

---

### Task 3: `config.py` — quota config keys

**Files:**
- Modify: `src/debussy/config.py` (`DEFAULTS` ~line 47, `KNOWN_KEYS` ~line 180)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: config keys `quota_check` (bool, default `False`), `quota_command` (str), `quota_margin` (float `0.97`); `KNOWN_KEYS` also gains `pause_reason`, `paused_until`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_quota_defaults(project_dir):
    cfg = get_config()
    assert cfg["quota_check"] is False
    assert cfg["quota_margin"] == 0.97
    assert cfg["quota_command"] == "ccusage blocks --active --json --token-limit max"


@pytest.mark.parametrize("key", [
    "quota_check", "quota_command", "quota_margin", "pause_reason", "paused_until",
])
def test_quota_keys_known(key):
    assert key in KNOWN_KEYS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -k quota -v`
Expected: FAIL — `KeyError: 'quota_check'` and missing `KNOWN_KEYS` members.

- [ ] **Step 3: Write minimal implementation**

In `src/debussy/config.py`, add to the `DEFAULTS` dict (after `notify_conductor`):

```python
    "quota_check": False,
    "quota_command": "ccusage blocks --active --json --token-limit max",
    "quota_margin": 0.97,
```

Add to the `KNOWN_KEYS` set:

```python
    "quota_check", "quota_command", "quota_margin", "pause_reason", "paused_until",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (including the existing `test_known_keys_survive_clean_config` parametrization, which now also exercises the new keys).

- [ ] **Step 5: Commit**

```bash
git add src/debussy/config.py tests/test_config.py
git commit  # subject: "Add quota config keys and pause-state keys"  + trailers
```

---

### Task 4: `cli.py` — pause-state markers

**Files:**
- Modify: `src/debussy/cli.py` (`cmd_pause` ~248, `cmd_resume` ~276, `cmd_start` ~41)
- Test: `tests/test_cli_pause.py` (create)

**Interfaces:**
- Consumes: `set_config`.
- Produces: `cmd_pause` sets `pause_reason="manual"`, `paused_until=None`; `cmd_resume` and `cmd_start` clear `pause_reason=None`, `paused_until=None`. These markers let the watcher distinguish manual pauses (never auto-resumed) from quota pauses.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_pause.py`:

```python
"""Pause-state markers set by the CLI pause/resume/start commands."""

import types

import pytest

from debussy import cli
from debussy.config import get_config


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_pause_sets_manual_reason(project_dir, monkeypatch):
    monkeypatch.setattr(cli, "_kill_all_agents", lambda: None)
    cli.cmd_pause(types.SimpleNamespace())
    cfg = get_config()
    assert cfg["paused"] is True
    assert cfg["pause_reason"] == "manual"
    assert cfg.get("paused_until") is None


def test_resume_clears_quota_markers(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("pause_reason", "quota")
    set_config("paused_until", 123.0)
    cli.cmd_resume(types.SimpleNamespace())
    cfg = get_config()
    assert cfg["paused"] is False
    assert cfg.get("pause_reason") is None
    assert cfg.get("paused_until") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_pause.py -v`
Expected: FAIL — `pause_reason` not set / not cleared.

- [ ] **Step 3: Write minimal implementation**

In `cmd_pause` (after `set_config("paused", True)`):

```python
    set_config("pause_reason", "manual")
    set_config("paused_until", None)
```

In `cmd_resume` (after `set_config("paused", False)`):

```python
    set_config("pause_reason", None)
    set_config("paused_until", None)
```

In `cmd_start`, both the paused and unpaused branches already call `set_config("paused", ...)`. Immediately after that if/else, add:

```python
    set_config("pause_reason", None)
    set_config("paused_until", None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli_pause.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/cli.py tests/test_cli_pause.py
git commit  # subject: "Mark pause reason on manual pause/resume/start"  + trailers
```

---

### Task 5: `watcher.py` — quota pause/resume state machine

**Files:**
- Modify: `src/debussy/watcher.py` (`__init__` ~30-50; add methods; imports ~12-23)
- Test: `tests/test_watcher.py` (create)

**Interfaces:**
- Consumes: `check_quota`, `QuotaStatus`, `QUOTA_DEFAULT_COOLDOWN` from `quota`; `set_config`, `get_config`; existing `_remove_agent`, `delete_task_branch`, `release_task`, `add_comment`, `get_db`.
- Produces (methods on `Watcher`):
  - `_clear_quota_pause()` → sets `paused=False`, `pause_reason=None`, `paused_until=None`.
  - `_pause_running_agents(comment: str)` → stops every running agent, resets active tasks to pending, removes worktrees, deletes developer branches.
  - `_enter_quota_pause(reset_at: float | None, source: str, status=None)` → resolves `reset_at` (arg → ccusage `endTime` → `now + QUOTA_DEFAULT_COOLDOWN`), pauses, kills workers.
  - `_maybe_auto_resume()` → at/after `paused_until`, re-verify and clear or extend.
  - `_warn_quota_unavailable(now: float)` → rate-limited warning.
  - New `__init__` fields: `self._last_quota_check = 0.0`, `self._quota_warned = 0.0`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_watcher.py`:

```python
"""Watcher quota pause/resume state machine (methods tested in isolation)."""

import types

import pytest

from debussy import watcher as watcher_mod
from debussy.watcher import Watcher
from debussy.quota import QuotaStatus


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _blank_watcher():
    w = Watcher.__new__(Watcher)
    w.running = {}
    w.used_names = set()
    w._cached_windows = None
    w._last_quota_check = 0.0
    w._quota_warned = 0.0
    w.failures = {}
    return w


def test_enter_quota_pause_sets_state(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._enter_quota_pause(1500.0, "quota")
    cfg = get_config()
    assert cfg["paused"] is True
    assert cfg["pause_reason"] == "quota"
    assert cfg["paused_until"] == 1500.0


def test_enter_quota_pause_resolves_none_via_ccusage(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 2222.0, 9, 10))
    w._enter_quota_pause(None, "wall-hit")
    assert get_config()["paused_until"] == 2222.0


def test_enter_quota_pause_falls_back_to_cooldown(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: None)
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._enter_quota_pause(None, "wall-hit")
    assert get_config()["paused_until"] == 1000.0 + 3600


def test_auto_resume_noop_before_reset(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 5000.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._maybe_auto_resume()
    assert get_config()["paused"] is True


def test_auto_resume_clears_when_quota_back(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 500.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(False, 9000.0, 1, 10))
    w._maybe_auto_resume()
    assert get_config()["paused"] is False
    assert get_config().get("pause_reason") is None


def test_auto_resume_extends_when_still_capped(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 500.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 8000.0, 10, 10))
    w._maybe_auto_resume()
    assert get_config()["paused"] is True
    assert get_config()["paused_until"] == 8000.0


def test_auto_resume_ignores_manual_pause(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "manual")
    set_config("paused_until", 100.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._maybe_auto_resume()
    assert get_config()["paused"] is True


def test_auto_resume_releases_when_feature_disabled(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 100.0); set_config("quota_check", False)
    w = _blank_watcher()
    w._maybe_auto_resume()
    assert get_config()["paused"] is False


def test_pause_running_agents_stops_and_clears(project_dir, monkeypatch):
    w = _blank_watcher()
    stopped = []
    agent = types.SimpleNamespace(
        task="PRJ-2", role="reviewer", name="reviewer-y",
        worktree_path="", window_id="",
    )
    agent.stop = lambda: stopped.append(agent.name)
    agent.cleanup = lambda: None
    w.running = {"reviewer:PRJ-2": agent}
    w.used_names = {"reviewer-y"}
    monkeypatch.setattr(watcher_mod, "get_task_status", lambda t: "pending")
    monkeypatch.setattr(w, "save_state", lambda: None)
    w._pause_running_agents("paused: test")
    assert stopped == ["reviewer-y"]
    assert w.running == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_watcher.py -v`
Expected: FAIL — the new methods do not exist yet.

- [ ] **Step 3: Write minimal implementation**

In `src/debussy/watcher.py` imports, add only the genuinely new names:

```python
from .config import set_config          # add to the existing `from .config import (...)` block
from .quota import check_quota, QUOTA_DEFAULT_COOLDOWN
```

(`release_task`, `get_db`, `add_comment` are already imported at line 18; `get_task_status` at line 11; `delete_task_branch` at line 23; `subprocess`/`time` at lines 6-7 — do not re-import these.)

In `Watcher.__init__`, add near the other counters:

```python
        self._last_quota_check = 0.0
        self._quota_warned = 0.0
```

Add these methods to `Watcher`:

```python
    def _clear_quota_pause(self):
        set_config("paused", False)
        set_config("pause_reason", None)
        set_config("paused_until", None)

    def _warn_quota_unavailable(self, now: float):
        from .quota import QUOTA_CHECK_INTERVAL
        if now - self._quota_warned >= QUOTA_CHECK_INTERVAL:
            self._quota_warned = now
            log("Quota check unavailable (ccusage) — proceeding", "⚠️")

    def _pause_running_agents(self, comment: str):
        for key, agent in list(self.running.items()):
            agent.stop()
            if get_task_status(agent.task) == STATUS_ACTIVE:
                with get_db() as db:
                    add_comment(db, agent.task, "watcher", comment)
                    release_task(db, agent.task)
            self._remove_agent(key, agent)
            if agent.role == "developer":
                try:
                    delete_task_branch(agent.task)
                except (subprocess.SubprocessError, OSError):
                    pass
        self.save_state()

    def _enter_quota_pause(self, reset_at, source: str, status=None):
        cfg = get_config()
        if reset_at is None:
            probe = status or check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
            reset_at = probe.reset_at if probe else None
        if reset_at is None:
            reset_at = time.time() + QUOTA_DEFAULT_COOLDOWN
        detail = f"used {status.used}/{status.limit}" if status else source
        log(f"Quota pause ({source}, {detail}); resuming at {int(reset_at)}", "🪫")
        self._pause_running_agents("Paused: quota limit reached")
        set_config("paused", True)
        set_config("pause_reason", "quota")
        set_config("paused_until", reset_at)

    def _maybe_auto_resume(self):
        cfg = get_config()
        if not cfg.get("paused") or cfg.get("pause_reason") != "quota":
            return
        if not cfg.get("quota_check"):
            self._clear_quota_pause()
            return
        until = cfg.get("paused_until")
        if until is None or time.time() < until:
            return
        status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
        if status is None:
            self._clear_quota_pause()
            return
        if status.exhausted:
            set_config("paused_until", status.reset_at or time.time() + QUOTA_DEFAULT_COOLDOWN)
        else:
            self._last_quota_check = time.time()
            self._clear_quota_pause()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_watcher.py -v`
Expected: PASS (8 cases).

- [ ] **Step 5: Commit**

```bash
git add src/debussy/watcher.py tests/test_watcher.py
git commit  # subject: "Add watcher quota pause/resume state machine"  + trailers
```

---

### Task 6: `watcher.py` — proactive gate + loop wiring

**Files:**
- Modify: `src/debussy/watcher.py` (add `_quota_gate`; `run()` loop ~357-379)
- Test: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `check_quota`, `QUOTA_CHECK_INTERVAL`, `_enter_quota_pause`, `_maybe_auto_resume`.
- Produces: `_quota_gate() -> QuotaStatus | None` (fresh exhausted status, else None). `run()` calls `_maybe_auto_resume()` before the pause gate; when not paused, consults `_quota_gate()` and either enters a quota pause or runs `release_ready`/`check_pipeline`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_watcher.py`:

```python
def test_quota_gate_disabled_returns_none(project_dir):
    w = _blank_watcher()
    assert w._quota_gate() is None  # quota_check defaults to False


def test_quota_gate_respects_interval(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    w._last_quota_check = 999.0
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)  # <60s since last
    called = []
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: called.append(1))
    assert w._quota_gate() is None
    assert called == []


def test_quota_gate_returns_status_when_exhausted(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 5.0, 10, 10))
    status = w._quota_gate()
    assert status is not None and status.exhausted is True


def test_quota_gate_none_when_healthy(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(False, 5.0, 1, 10))
    assert w._quota_gate() is None


def test_quota_gate_warns_and_returns_none_on_unavailable(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: None)
    warned = []
    monkeypatch.setattr(w, "_warn_quota_unavailable", lambda now: warned.append(now))
    assert w._quota_gate() is None
    assert warned == [10_000.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_watcher.py -k quota_gate -v`
Expected: FAIL — `_quota_gate` not defined.

- [ ] **Step 3: Write minimal implementation**

Add the method to `Watcher`:

```python
    def _quota_gate(self):
        from .quota import QUOTA_CHECK_INTERVAL
        cfg = get_config()
        if not cfg.get("quota_check"):
            return None
        now = time.time()
        if now - self._last_quota_check < QUOTA_CHECK_INTERVAL:
            return None
        self._last_quota_check = now
        status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
        if status is None:
            self._warn_quota_unavailable(now)
            return None
        return status if status.exhausted else None
```

In `run()`, replace the existing pause-gated block:

```python
                if not get_config().get("paused", False):
                    self._refresh_tmux_cache()
                    release_ready(self)
                    check_pipeline(self)
```

with:

```python
                self._maybe_auto_resume()
                if not get_config().get("paused", False):
                    self._refresh_tmux_cache()
                    status = self._quota_gate()
                    if status is not None:
                        self._enter_quota_pause(status.reset_at, "quota", status)
                    else:
                        release_ready(self)
                        check_pipeline(self)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_watcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/watcher.py tests/test_watcher.py
git commit  # subject: "Wire proactive quota gate + auto-resume into watcher loop"  + trailers
```

---

### Task 7: `watcher.py` — reactive backstop in `cleanup_finished`

**Files:**
- Modify: `src/debussy/watcher.py` (`cleanup_finished` ~211-259; `run()` ~361)
- Test: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `detect_limit_signal`, `read_log_tail`.
- Produces: `cleanup_finished()` now returns `float | None | "HIT"` — specifically it returns the earliest reset-ts among quota-signal deaths this tick, or a "hit-without-ts" marker, or `None`. Concretely it returns a `tuple[bool, float | None]` `(hit, earliest_ts)`. `run()` calls `_enter_quota_pause(earliest_ts, "wall-hit")` when `hit`. Quota-signal deaths roll back their `self.failures[task]` increment.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_watcher.py`. These drive `cleanup_finished` with a single dead, non-tmux agent whose log tail is stubbed:

```python
def _dead_agent(task="PRJ-1", role="developer"):
    # started_at close to the stubbed clock (elapsed 5s < MIN_AGENT_RUNTIME=30)
    # so cleanup_finished routes into the death branch, not the completed branch.
    agent = types.SimpleNamespace(
        task=task, role=role, name=f"{role}-x", tmux=False, window_id="",
        worktree_path="", log_path="/tmp/x.log", claimed=True,
        started_at=1000.0, proc=None,
    )
    agent.is_alive = lambda cached=None: False
    agent.stop = lambda: None
    agent.cleanup = lambda: None
    return agent


def _prime_cleanup(monkeypatch, w, tail):
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1005.0)  # elapsed 5s
    monkeypatch.setattr(watcher_mod, "read_log_tail", lambda p: tail)
    monkeypatch.setattr(watcher_mod, "get_task_status", lambda t: "pending")
    monkeypatch.setattr(watcher_mod, "ensure_stage_transition", lambda *a: False)
    monkeypatch.setattr(watcher_mod, "comment_on_task", lambda *a: None)
    monkeypatch.setattr(watcher_mod, "format_death_comment", lambda *a: "")
    monkeypatch.setattr(watcher_mod, "delete_task_branch", lambda t: None)
    monkeypatch.setattr(w, "save_state", lambda: None)
    monkeypatch.setattr(w, "_save_empty_branch_retries", lambda: None)


def test_cleanup_returns_hit_on_limit_signal(project_dir, monkeypatch):
    w = _blank_watcher()
    w.running = {"developer:PRJ-1": _dead_agent()}
    _prime_cleanup(monkeypatch, w, "Claude usage limit reached. resets 3pm")
    hit, ts = w.cleanup_finished()
    assert hit is True
    assert ts is None


def test_cleanup_no_hit_on_normal_death(project_dir, monkeypatch):
    w = _blank_watcher()
    w.running = {"developer:PRJ-1": _dead_agent()}
    _prime_cleanup(monkeypatch, w, "Traceback: something unrelated crashed")
    hit, ts = w.cleanup_finished()
    assert hit is False


def test_cleanup_rolls_back_failure_on_quota_death(project_dir, monkeypatch):
    w = _blank_watcher()
    w.running = {"developer:PRJ-1": _dead_agent()}
    _prime_cleanup(monkeypatch, w, "usage limit reached")
    w.cleanup_finished()
    assert w.failures.get("PRJ-1", 0) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_watcher.py -k cleanup -v`
Expected: FAIL — `cleanup_finished` returns `None`, not a tuple; no rollback.

- [ ] **Step 3: Write minimal implementation**

Add the import: `from .quota import ..., detect_limit_signal` (extend the existing `from .quota import` line).

In `cleanup_finished`, initialise trackers at the top:

```python
        cleaned = False
        transitioned = False
        quota_hit = False
        quota_ts = None
```

The death branch already computes `log_tail` as a local (`watcher.py:241`) right after the
`self.failures[agent.task] += 1` increment (`:239`). Insert the backstop detection *between*
that existing `log_tail = read_log_tail(...)` line and the following
`comment = format_death_comment(...)` line — no hoisting needed. The current pair:

```python
                    log_tail = read_log_tail(agent.log_path) if agent.log_path else ""
                    comment = format_death_comment(agent.name, int(elapsed), str(task_status), log_tail)
```

becomes:

```python
                    log_tail = read_log_tail(agent.log_path) if agent.log_path else ""
                    hit, ts = detect_limit_signal(log_tail)
                    if hit:
                        quota_hit = True
                        if ts is not None:
                            quota_ts = ts if quota_ts is None else min(quota_ts, ts)
                        self.failures[agent.task] = max(0, self.failures.get(agent.task, 0) - 1)
                    comment = format_death_comment(agent.name, int(elapsed), str(task_status), log_tail)
```

At the end of `cleanup_finished`, change the final lines to return the trackers:

```python
        if cleaned:
            self.save_state()
            self._save_empty_branch_retries()
        return quota_hit, quota_ts
```

In `run()`, consume the return right after the `cleanup_finished()` call:

```python
                quota_hit, quota_ts = self.cleanup_finished()
```

and, after `reset_orphaned(self)`, before `_maybe_auto_resume()`:

```python
                if quota_hit:
                    self._enter_quota_pause(quota_ts, "wall-hit")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_watcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/watcher.py tests/test_watcher.py
git commit  # subject: "Add reactive usage-limit backstop with failure rollback"  + trailers
```

---

### Task 8: Documentation + full suite

**Files:**
- Modify: `CLAUDE.md` (Commands section)
- Test: whole suite

**Interfaces:** none (docs + verification).

- [ ] **Step 1: Document the config keys and prerequisite**

In `CLAUDE.md`, under the `debussy config` command list, add:

```
debussy config quota_check true              # Enable quota-aware pause (requires ccusage: npm i -g ccusage)
debussy config quota_command "<cmd>"         # Override the ccusage invocation
debussy config quota_margin 0.97             # Pause when used >= margin * estimated ceiling
```

And add one line to the pipeline/overview notes: "With `quota_check` enabled, the watcher pauses worker spawns at the margin and auto-resumes after the session/weekly window resets."

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS — all existing tests plus `test_quota.py`, `test_watcher.py`, `test_cli_pause.py`, new `test_config.py` cases.

- [ ] **Step 3: Import smoke check**

Run: `python -c "import debussy.watcher, debussy.quota, debussy.cli, debussy.config"`
Expected: no ImportError.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit  # subject: "Document quota-aware pause config and ccusage prerequisite"  + trailers
```

---

## Self-Review

**Spec coverage:**
- Proactive ccusage gate at 97% → Tasks 1, 6. ✓
- Fail-open on any ccusage failure → Task 1 (parametrized) + Task 6 (gate warns). ✓
- Reactive backstop (weekly + estimate miss) → Tasks 2, 7. ✓
- Kill in-flight workers + reset tasks + delete dev branches → Task 5 (`_pause_running_agents`). ✓
- Auto-resume with re-verify / extend / feature-disabled release → Task 5. ✓
- Manual-vs-quota pause distinction → Task 4 markers + Task 5 `_maybe_auto_resume` guard. ✓
- Failure-count rollback on quota death → Task 7. ✓
- 3 config keys + pause-state keys in KNOWN_KEYS → Task 3. ✓
- Constants (interval/cooldown/timeout) not config → Task 1. ✓
- Docs + prerequisite → Task 8. ✓

**Refinement vs. spec (recorded, within design intent):** the spec's `detect_limit_signal(log_tail, now) -> float | None` becomes `detect_limit_signal(log_tail) -> tuple[bool, float | None]`, and reset-time resolution (ccusage `endTime` → cooldown) moves into `_enter_quota_pause`. This exploits the verified fact that ccusage's `endTime` is a reliable session reset, removing the need for a fragile human-clock-time parser. Weekly precision remains best-effort (self-corrects via the re-verify/extend loop) — the honest limitation the spec already flagged.

**Placeholder scan:** no TBD/TODO; every code and test step is concrete. ✓

**Type consistency:** `check_quota(command, margin)`, `QuotaStatus(exhausted, reset_at, used, limit)`, `detect_limit_signal -> (hit, reset_at)`, `_enter_quota_pause(reset_at, source, status=None)`, `cleanup_finished -> (quota_hit, quota_ts)` used consistently across Tasks 1–7. ✓
