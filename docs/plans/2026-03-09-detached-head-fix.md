# Detached HEAD Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent agents from running in the main repo when worktree creation fails, which causes HEAD detachment.

**Architecture:** Fail-fast in `spawn_agent` when `create_agent_worktree` returns empty for roles that need worktrees. Add worktree validation to agent prompts as defense-in-depth. Fix integrator's detached checkout to use a local branch.

**Tech Stack:** Python, git worktrees, agent prompt templates (Markdown)

---

### Task 1: Add spawner test for worktree failure abort

**Files:**
- Create: `tests/test_spawner.py`
- Modify: `src/debussy/spawner.py:165-211`

**Step 1: Write the failing test**

```python
"""Tests for agent spawning."""

import unittest
from unittest.mock import MagicMock, patch


class TestSpawnAgentWorktreeFailure(unittest.TestCase):
    def _make_watcher(self):
        watcher = MagicMock()
        watcher.running = {}
        watcher.failures = {}
        watcher.spawn_counts = {}
        watcher.used_names = set()
        watcher._cached_windows = None
        return watcher

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="developer-bach")
    def test_spawn_aborts_when_worktree_fails_for_developer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertFalse(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 1)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_reviewer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "reviewer", "bd-001", "stage:reviewing")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="integrator-bach")
    def test_spawn_aborts_when_worktree_fails_for_integrator(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "integrator", "bd-001", "stage:merging")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="tester-bach")
    def test_spawn_aborts_when_worktree_fails_for_tester(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "tester", "bd-001", "stage:acceptance")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="security-reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_security_reviewer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "security-reviewer", "bd-001", "stage:security-review")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tomek/dev/debussy && python -m pytest tests/test_spawner.py -v`
Expected: FAIL — spawn_agent currently proceeds even when worktree_path is empty.

**Step 3: Implement worktree failure guard in spawn_agent**

In `src/debussy/spawner.py`, after line 180 (`worktree_path = create_agent_worktree(...)`) and before line 181, add:

```python
WORKTREE_REQUIRED_ROLES = {"developer", "reviewer", "security-reviewer", "integrator", "tester"}

# (add this check after worktree_path = create_agent_worktree(...))
if not worktree_path and role in WORKTREE_REQUIRED_ROLES:
    log(f"Worktree creation failed for {agent_name}, aborting spawn", "💥")
    watcher.used_names.discard(agent_name)
    watcher.failures[bead_id] = watcher.failures.get(bead_id, 0) + 1
    return False
```

Define `WORKTREE_REQUIRED_ROLES` as a module-level constant near `MAX_TOTAL_SPAWNS`.

**Step 4: Run test to verify it passes**

Run: `cd /Users/tomek/dev/debussy && python -m pytest tests/test_spawner.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add tests/test_spawner.py src/debussy/spawner.py
git commit -m "[debussy] abort agent spawn when worktree creation fails

Prevents agents from running in the main repo directory when
worktree creation fails, which was causing HEAD detachment."
```

---

### Task 2: Add worktree validation to agent prompts

**Files:**
- Modify: `src/debussy/prompts/developer.md:3-4`
- Modify: `src/debussy/prompts/reviewer.md:6-7`
- Modify: `src/debussy/prompts/integrator.md:3`

**Step 1: Add worktree safety check to developer.md**

Insert after line 4 (`EXECUTE THESE STEPS NOW:`), before the numbered steps:

```
0. SAFETY CHECK: run `git rev-parse --show-toplevel` — the path MUST contain `.debussy-worktrees/`. If it does NOT, exit immediately: "ERROR: Running in main repo instead of worktree — aborting." Set status blocked.
```

**Step 2: Add worktree safety check to reviewer.md**

Insert after line 5 (`1. bd show <BEAD_ID> — read the task description carefully`), as a new step before step 2. Renumber subsequent steps.

```
2. SAFETY CHECK: run `git rev-parse --show-toplevel` — the path MUST contain `.debussy-worktrees/`. If it does NOT, exit immediately: "ERROR: Running in main repo instead of worktree — aborting." Set status blocked.
```

Actually — insert before step 1 as step 0, to catch it before any work:

```
0. SAFETY CHECK: run `git rev-parse --show-toplevel` — the path MUST contain `.debussy-worktrees/`. If it does NOT, exit immediately: "ERROR: Running in main repo instead of worktree — aborting." Set status blocked.
```

**Step 3: Add worktree safety check to integrator.md**

Insert before step 1:

```
0. SAFETY CHECK: run `git rev-parse --show-toplevel` — the path MUST contain `.debussy-worktrees/`. If it does NOT, exit immediately: "ERROR: Running in main repo instead of worktree — aborting." Set status blocked.
```

**Step 4: Fix integrator detached checkout**

In `integrator.md`, change step 3 from:
```
3. git fetch origin && git checkout origin/<BASE_BRANCH>
```
to:
```
3. git fetch origin
```

Remove the `git checkout` — the integrator worktree is already detached at `origin/<BASE_BRANCH>` by `create_agent_worktree`. The checkout is redundant and harmful.

Also update the `IF PUSH FAILS` retry block — remove `git checkout origin/<BASE_BRANCH>` from the retry steps since the worktree is already at the right ref. Change:
```
  git fetch origin
  git checkout origin/<BASE_BRANCH>
  git merge origin/feature/<BEAD_ID> --no-ff
```
to:
```
  git fetch origin
  git reset --hard origin/<BASE_BRANCH>
  git merge origin/feature/<BEAD_ID> --no-ff
```

And remove the `IMPORTANT: You are on a detached HEAD...` line since the safety check + worktree setup handles this.

**Step 5: Commit**

```bash
git add src/debussy/prompts/developer.md src/debussy/prompts/reviewer.md src/debussy/prompts/integrator.md
git commit -m "[debussy] add worktree validation to agent prompts

Defense-in-depth: agents verify they are in a worktree before
starting work. Also removes redundant checkout from integrator
since the worktree is already set up at the correct ref."
```

---

### Task 3: Add retry with prune in create_agent_worktree

**Files:**
- Modify: `src/debussy/spawner.py:40-64`
- Modify: `tests/test_spawner.py`

**Step 1: Write the failing test**

Add to `tests/test_spawner.py`:

```python
class TestCreateAgentWorktreeRetry(unittest.TestCase):
    @patch("debussy.spawner.get_config", return_value={"base_branch": "master"})
    @patch("debussy.spawner.create_worktree")
    @patch("debussy.spawner.subprocess")
    def test_retries_once_after_failure(self, mock_subprocess, mock_create_wt, _cfg):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.SubprocessError = subprocess.SubprocessError
        mock_create_wt.side_effect = [
            subprocess.CalledProcessError(1, "git"),
            Path("/fake/worktree"),
        ]

        from debussy.spawner import create_agent_worktree

        result = create_agent_worktree("developer", "bd-001", "developer-bach")

        self.assertEqual(result, "/fake/worktree")
        self.assertEqual(mock_create_wt.call_count, 2)

    @patch("debussy.spawner.get_config", return_value={"base_branch": "master"})
    @patch("debussy.spawner.create_worktree")
    @patch("debussy.spawner.subprocess")
    def test_returns_empty_after_retry_failure(self, mock_subprocess, mock_create_wt, _cfg):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.SubprocessError = subprocess.SubprocessError
        mock_create_wt.side_effect = subprocess.CalledProcessError(1, "git")

        from debussy.spawner import create_agent_worktree

        result = create_agent_worktree("developer", "bd-001", "developer-bach")

        self.assertEqual(result, "")
        self.assertEqual(mock_create_wt.call_count, 2)
```

Add `import subprocess` and `from pathlib import Path` at the top of the test file.

**Step 2: Run test to verify it fails**

Run: `cd /Users/tomek/dev/debussy && python -m pytest tests/test_spawner.py::TestCreateAgentWorktreeRetry -v`
Expected: FAIL — no retry logic exists yet.

**Step 3: Add retry logic to create_agent_worktree**

In `src/debussy/spawner.py`, replace the except block in `create_agent_worktree` (lines 60-64):

```python
    except (subprocess.SubprocessError, OSError) as e:
        stderr = getattr(e, "stderr", "") or ""
        detail = f" — {stderr.strip()}" if stderr.strip() else ""
        log(f"Worktree creation failed for {agent_name}, retrying after prune: {e}{detail}", "⚠️")
        subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
        try:
            if role == "developer":
                wt = create_worktree(agent_name, f"feature/{bead_id}", start_point=f"origin/{base}", new_branch=True)
            elif role in ("reviewer", "security-reviewer"):
                wt = create_worktree(agent_name, f"origin/feature/{bead_id}", detach=True)
            elif role in ("integrator", "tester"):
                wt = create_worktree(agent_name, f"origin/{base}", detach=True)
            else:
                return ""
            return str(wt)
        except (subprocess.SubprocessError, OSError):
            log(f"Worktree creation failed after retry for {agent_name}", "⚠️")
            return ""
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tomek/dev/debussy && python -m pytest tests/test_spawner.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/debussy/spawner.py tests/test_spawner.py
git commit -m "[debussy] retry worktree creation once after prune on failure

Handles stale worktrees from previous sessions by pruning and
retrying before giving up."
```
