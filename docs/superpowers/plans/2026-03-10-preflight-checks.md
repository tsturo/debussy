# Pre-flight Checks & Failure Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent blind agent retries by validating config and git state before spawning, and writing actionable failure context to bead comments when blocking.

**Architecture:** New `preflight.py` module with pure validation functions called by `spawn_agent` before worktree creation. On agent death, `cleanup_finished` reads the last N lines of the agent log and writes a diagnostic comment to the bead.

**Tech Stack:** Python, subprocess (git/bd CLI), existing test patterns (unittest + MagicMock)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/debussy/preflight.py` | Create | Pre-flight validation functions |
| `src/debussy/spawner.py` | Modify | Call preflight before spawn |
| `src/debussy/watcher.py` | Modify | Write diagnostic comments on agent death/block |
| `src/debussy/pipeline_checker.py` | Modify | Pass log context to `_block_failed_bead` |
| `tests/test_preflight.py` | Create | Tests for validation functions |
| `tests/test_spawner.py` | Modify | Test preflight integration |

---

## Chunk 1: Pre-flight Validation Module

### Task 1: Create preflight validation functions

**Files:**
- Create: `src/debussy/preflight.py`
- Create: `tests/test_preflight.py`

- [ ] **Step 1: Write failing tests for `check_base_branch`**

```python
# tests/test_preflight.py
import subprocess
from unittest.mock import MagicMock, patch

from debussy.preflight import check_base_branch, check_remote_ref


class TestCheckBaseBranch:
    def test_returns_none_when_base_branch_set_and_exists(self):
        with patch("debussy.preflight.get_config", return_value={"base_branch": "feature/foo"}):
            with patch("debussy.preflight.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                assert check_base_branch() is None

    def test_returns_error_when_base_branch_not_set(self):
        with patch("debussy.preflight.get_config", return_value={}):
            result = check_base_branch()
            assert result is not None
            assert "not configured" in result

    def test_returns_error_when_remote_ref_missing(self):
        with patch("debussy.preflight.get_config", return_value={"base_branch": "feature/foo"}):
            with patch("debussy.preflight.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=128)
                result = check_base_branch()
                assert result is not None
                assert "not found" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_preflight.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write failing tests for `check_remote_ref`**

```python
class TestCheckRemoteRef:
    def test_returns_none_when_ref_exists(self):
        with patch("debussy.preflight.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_remote_ref("origin/feature/bd-001") is None

    def test_returns_error_when_ref_missing(self):
        with patch("debussy.preflight.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            result = check_remote_ref("origin/feature/bd-001")
            assert result is not None
            assert "bd-001" in result
```

- [ ] **Step 4: Write failing tests for `preflight_spawn`**

```python
class TestPreflightSpawn:
    def test_developer_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value="base_branch not configured") as mock:
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("developer", "bd-001")
            assert result is not None
            mock.assert_called_once()

    def test_reviewer_checks_feature_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            with patch("debussy.preflight.check_remote_ref", return_value="ref not found") as mock:
                from debussy.preflight import preflight_spawn
                result = preflight_spawn("reviewer", "bd-001")
                assert result is not None
                mock.assert_called_once_with("origin/feature/bd-001")

    def test_investigator_only_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            with patch("debussy.preflight.check_remote_ref") as mock:
                from debussy.preflight import preflight_spawn
                result = preflight_spawn("investigator", "bd-001")
                assert result is None
                mock.assert_not_called()

    def test_developer_passes_all_checks(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("developer", "bd-001")
            assert result is None

    def test_integrator_checks_base_branch(self):
        with patch("debussy.preflight.check_base_branch", return_value=None):
            from debussy.preflight import preflight_spawn
            result = preflight_spawn("integrator", "bd-001")
            assert result is None
```

- [ ] **Step 5: Implement `preflight.py`**

```python
# src/debussy/preflight.py
"""Pre-flight validation before agent spawning."""

import subprocess

from .config import get_config


def check_base_branch() -> str | None:
    base = get_config().get("base_branch")
    if not base:
        return "base_branch not configured — run: debussy config base_branch <branch>"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{base}"],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return f"base_branch origin/{base} not found on remote"
    except (subprocess.SubprocessError, OSError) as e:
        return f"git check failed: {e}"
    return None


def check_remote_ref(ref: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return f"ref {ref} not found"
    except (subprocess.SubprocessError, OSError) as e:
        return f"git check failed: {e}"
    return None


NEEDS_FEATURE_BRANCH = {"reviewer", "security-reviewer"}


def preflight_spawn(role: str, bead_id: str) -> str | None:
    err = check_base_branch()
    if err:
        return err
    if role in NEEDS_FEATURE_BRANCH:
        err = check_remote_ref(f"origin/feature/{bead_id}")
        if err:
            return err
    return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_preflight.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/debussy/preflight.py tests/test_preflight.py
git commit -m "[debussy] add pre-flight validation for agent spawning"
```

---

## Chunk 2: Integrate Pre-flight into Spawner

### Task 2: Call preflight from `spawn_agent`

**Files:**
- Modify: `src/debussy/spawner.py:172-192`
- Modify: `tests/test_spawner.py`

- [ ] **Step 1: Write failing test for preflight integration**

Add to `tests/test_spawner.py`:

```python
class TestSpawnAgentPreflight(unittest.TestCase):
    def _make_watcher(self):
        watcher = MagicMock()
        watcher.running = {}
        watcher.failures = {}
        watcher.spawn_counts = {}
        watcher.used_names = set()
        watcher._cached_windows = None
        return watcher

    @patch("debussy.spawner.preflight_spawn", return_value="base_branch not configured")
    def test_spawn_aborts_on_preflight_failure(self, _preflight):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertFalse(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 1)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="/fake/wt")
    @patch("debussy.spawner.get_agent_name", return_value="developer-bach")
    @patch("debussy.spawner.get_base_branch", return_value="master")
    @patch("debussy.spawner.get_user_message", return_value="msg")
    @patch("debussy.spawner.get_system_prompt", return_value="prompt")
    @patch("debussy.spawner.get_config", return_value={"use_tmux_windows": False})
    @patch("debussy.spawner.record_event")
    @patch("debussy.spawner._spawn_background")
    def test_spawn_proceeds_after_preflight_passes(
        self, mock_bg, _event, _cfg, _sys, _msg, _base, _name, _wt, _preflight
    ):
        from debussy.spawner import spawn_agent

        mock_bg.return_value = MagicMock()
        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertTrue(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_spawner.py::TestSpawnAgentPreflight -v`
Expected: FAIL (preflight_spawn not imported)

- [ ] **Step 3: Modify `spawn_agent` in `spawner.py`**

Add import at top of `spawner.py`:
```python
from .preflight import preflight_spawn
```

Insert preflight check in `spawn_agent` after the existing guard checks (line 182) and before `get_agent_name` (line 184):

```python
    preflight_err = preflight_spawn(role, bead_id)
    if preflight_err:
        log(f"Preflight failed for {bead_id}: {preflight_err}", "🚫")
        watcher.failures[bead_id] = watcher.failures.get(bead_id, 0) + 1
        return False
```

- [ ] **Step 4: Run all spawner tests**

Run: `python3 -m pytest tests/test_spawner.py -v`
Expected: all PASS

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/spawner.py tests/test_spawner.py
git commit -m "[debussy] integrate pre-flight checks into spawn_agent"
```

---

## Chunk 3: Diagnostic Comments on Failure

### Task 3: Write agent log tail to bead comments on death and block

**Files:**
- Modify: `src/debussy/watcher.py:313-323`
- Modify: `src/debussy/pipeline_checker.py:159-170`
- Create: `src/debussy/diagnostics.py`
- Create: `tests/test_diagnostics.py`

- [ ] **Step 1: Write failing tests for `read_log_tail`**

```python
# tests/test_diagnostics.py
import tempfile
from pathlib import Path

from debussy.diagnostics import read_log_tail


class TestReadLogTail:
    def test_reads_last_n_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(20):
                f.write(f"line {i}\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=5)
            assert "line 19" in result
            assert "line 15" in result
            assert "line 14" not in result

    def test_returns_empty_for_missing_file(self):
        result = read_log_tail("/nonexistent/path.log")
        assert result == ""

    def test_returns_full_content_when_short(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("only line\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=10)
            assert "only line" in result

    def test_truncates_long_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("x" * 500 + "\n")
            f.flush()
            result = read_log_tail(f.name, max_lines=5, max_line_len=100)
            assert len(result.splitlines()[0]) <= 103  # 100 + "..."
```

- [ ] **Step 2: Write failing tests for `format_death_comment`**

```python
from debussy.diagnostics import format_death_comment


class TestFormatDeathComment:
    def test_includes_agent_name_and_elapsed(self):
        result = format_death_comment("developer-bach", 5, "open", "error on line 1\ncrash")
        assert "developer-bach" in result
        assert "5s" in result

    def test_includes_log_tail(self):
        result = format_death_comment("developer-bach", 5, "open", "some error output")
        assert "some error output" in result

    def test_handles_empty_log(self):
        result = format_death_comment("developer-bach", 5, "open", "")
        assert "developer-bach" in result
        assert "no log" in result.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `diagnostics.py`**

```python
# src/debussy/diagnostics.py
"""Failure diagnostics for agent deaths and blocks."""

import subprocess

LOG_TAIL_LINES = 15
LOG_MAX_LINE_LEN = 200


def read_log_tail(log_path: str, max_lines: int = LOG_TAIL_LINES, max_line_len: int = LOG_MAX_LINE_LEN) -> str:
    try:
        with open(log_path) as f:
            lines = f.readlines()
    except OSError:
        return ""
    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    truncated = []
    for line in tail:
        line = line.rstrip("\n")
        if len(line) > max_line_len:
            line = line[:max_line_len] + "..."
        truncated.append(line)
    return "\n".join(truncated)


def format_death_comment(agent_name: str, elapsed: int, status: str, log_tail: str) -> str:
    parts = [f"Agent {agent_name} died after {elapsed}s (status={status})."]
    if log_tail:
        parts.append(f"Last output:\n{log_tail}")
    else:
        parts.append("No log output captured.")
    return "\n".join(parts)


def comment_on_bead(bead_id: str, text: str):
    try:
        subprocess.run(
            ["bd", "comment", bead_id, text],
            capture_output=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_diagnostics.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/diagnostics.py tests/test_diagnostics.py
git commit -m "[debussy] add diagnostics module for agent failure context"
```

### Task 4: Wire diagnostics into watcher and pipeline_checker

**Files:**
- Modify: `src/debussy/watcher.py:313-323`
- Modify: `src/debussy/pipeline_checker.py:159-170`

- [ ] **Step 1: Add diagnostic comment on agent death in `cleanup_finished`**

In `watcher.py`, add import:
```python
from .diagnostics import comment_on_bead, format_death_comment, read_log_tail
```

Replace the death handling block (lines 313-323) — after `self.failures[agent.bead] = ...` and the log line, add:

```python
                    log_tail = read_log_tail(agent.log_path) if agent.log_path else ""
                    comment = format_death_comment(agent.name, int(elapsed), str(bead_status), log_tail)
                    comment_on_bead(agent.bead, comment)
```

This goes after the existing `log(...)` call (line 315) and before the `if bead_status == STATUS_IN_PROGRESS:` check (line 316).

- [ ] **Step 2: Add diagnostic comment on block in `_block_failed_bead`**

In `pipeline_checker.py`, add import:
```python
from .diagnostics import comment_on_bead
```

In `_block_failed_bead` (line 163), after `log(...)`, add:

```python
    comment_on_bead(bead_id, f"Blocked: max {reason} reached. Needs conductor intervention.")
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/debussy/watcher.py src/debussy/pipeline_checker.py
git commit -m "[debussy] write diagnostic comments on agent death and block"
```

---

## Chunk 4: Include pre-flight error in bead comment

### Task 5: Comment preflight failures on beads

**Files:**
- Modify: `src/debussy/spawner.py`

- [ ] **Step 1: Add diagnostic comment when preflight fails**

In `spawner.py`, add import:
```python
from .diagnostics import comment_on_bead
```

In the preflight failure block (added in Task 2), after the log line, add:

```python
        comment_on_bead(bead_id, f"Spawn blocked: {preflight_err}")
```

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add src/debussy/spawner.py
git commit -m "[debussy] comment preflight failures on beads for conductor visibility"
```
