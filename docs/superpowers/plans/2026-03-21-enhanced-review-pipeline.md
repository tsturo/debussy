# Enhanced Review Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add specialized post-merge review stages (UX, performance) and parallel batch acceptance reviewers (architecture, skeptic, enhanced tester) to the Debussy pipeline.

**Architecture:** Two new tag-gated stages after merging (`ux_review`, `perf_review`). Dependencies unblock after merging instead of at `done`. Acceptance stage spawns 3 agents in parallel. Merging is no longer a terminal stage — it flows into tag-gated post-merge stages.

**Tech Stack:** Python, SQLite (takt), tmux, Claude Code CLI

**Spec:** `docs/superpowers/specs/2026-03-21-enhanced-review-pipeline-design.md`

---

### Task 1: Add new stage constants and config maps

**Files:**
- Modify: `src/debussy/config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_stages.py
from debussy.config import (
    STAGE_UX_REVIEW, STAGE_PERF_REVIEW,
    STAGE_TO_ROLE, NEXT_STAGE, STAGE_SHORT,
    POST_MERGE_STAGES, STAGE_REQUIRED_TAGS, ACCEPTANCE_ROLES,
    DEFAULTS,
)


def test_ux_review_stage_constant():
    assert STAGE_UX_REVIEW == "ux_review"


def test_perf_review_stage_constant():
    assert STAGE_PERF_REVIEW == "perf_review"


def test_stage_to_role_includes_new_roles():
    assert STAGE_TO_ROLE[STAGE_UX_REVIEW] == "ux-reviewer"
    assert STAGE_TO_ROLE[STAGE_PERF_REVIEW] == "perf-reviewer"


def test_next_stage_merging_goes_to_ux_review():
    assert NEXT_STAGE["merging"] == "ux_review"


def test_next_stage_ux_review_goes_to_perf_review():
    assert NEXT_STAGE["ux_review"] == "perf_review"


def test_next_stage_perf_review_goes_to_done():
    assert NEXT_STAGE["perf_review"] == "done"


def test_stage_short_includes_new_stages():
    assert STAGE_SHORT[STAGE_UX_REVIEW] == "ux"
    assert STAGE_SHORT[STAGE_PERF_REVIEW] == "perf"


def test_post_merge_stages():
    assert "ux_review" in POST_MERGE_STAGES
    assert "perf_review" in POST_MERGE_STAGES
    assert "done" in POST_MERGE_STAGES


def test_stage_required_tags():
    assert STAGE_REQUIRED_TAGS["ux_review"] == "ux_review"
    assert STAGE_REQUIRED_TAGS["perf_review"] == "perf_review"


def test_acceptance_roles():
    assert ACCEPTANCE_ROLES == ["tester", "arch-reviewer", "skeptic"]


def test_defaults_include_new_role_models():
    models = DEFAULTS["role_models"]
    assert "ux-reviewer" in models
    assert "perf-reviewer" in models
    assert "arch-reviewer" in models
    assert "skeptic" in models


def test_defaults_include_new_max_role_agents():
    caps = DEFAULTS["max_role_agents"]
    assert "ux-reviewer" in caps
    assert "perf-reviewer" in caps
    assert "arch-reviewer" in caps
    assert "skeptic" in caps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_stages.py -v`
Expected: ImportError — `STAGE_UX_REVIEW` etc. not defined

- [ ] **Step 3: Implement the config changes**

In `src/debussy/config.py`, add after the existing stage constants (after line 32):

```python
STAGE_UX_REVIEW = "ux_review"
STAGE_PERF_REVIEW = "perf_review"
```

Add after `LABEL_PRIORITY` (after line 39):

```python
POST_MERGE_STAGES = {STAGE_UX_REVIEW, STAGE_PERF_REVIEW, STAGE_DONE}

STAGE_REQUIRED_TAGS = {
    STAGE_UX_REVIEW: "ux_review",
    STAGE_PERF_REVIEW: "perf_review",
}

ACCEPTANCE_ROLES = ["tester", "arch-reviewer", "skeptic"]
```

Update `STAGE_TO_ROLE` to add new mappings:

```python
STAGE_TO_ROLE = {
    STAGE_ACCEPTANCE: "tester",
    STAGE_MERGING: "integrator",
    STAGE_SECURITY_REVIEW: "security-reviewer",
    STAGE_REVIEWING: "reviewer",
    STAGE_DEVELOPMENT: "developer",
    STAGE_UX_REVIEW: "ux-reviewer",
    STAGE_PERF_REVIEW: "perf-reviewer",
}
```

Update `NEXT_STAGE`:

```python
NEXT_STAGE = {
    STAGE_BACKLOG: STAGE_DEVELOPMENT,
    STAGE_DEVELOPMENT: STAGE_REVIEWING,
    STAGE_REVIEWING: STAGE_MERGING,
    STAGE_SECURITY_REVIEW: STAGE_MERGING,
    STAGE_MERGING: STAGE_UX_REVIEW,
    STAGE_UX_REVIEW: STAGE_PERF_REVIEW,
    STAGE_PERF_REVIEW: STAGE_DONE,
    STAGE_ACCEPTANCE: STAGE_DONE,
}
```

Update `STAGE_SHORT`:

```python
STAGE_SHORT = {
    STAGE_BACKLOG: "backlog",
    STAGE_DEVELOPMENT: "dev",
    STAGE_REVIEWING: "rev",
    STAGE_SECURITY_REVIEW: "sec",
    STAGE_MERGING: "merge",
    STAGE_UX_REVIEW: "ux",
    STAGE_PERF_REVIEW: "perf",
    STAGE_ACCEPTANCE: "accept",
    STAGE_DONE: "done",
}
```

Update `DEFAULTS`:

```python
DEFAULTS = {
    "max_total_agents": 8,
    "use_tmux_windows": False,
    "agent_provider": "claude",
    "role_models": {
        "conductor": "claude-opus-4-6",
        "developer": "claude-sonnet-4-6",
        "reviewer": "claude-opus-4-6",
        "security-reviewer": "claude-opus-4-6",
        "integrator": "claude-sonnet-4-6",
        "tester": "claude-sonnet-4-6",
        "ux-reviewer": "claude-sonnet-4-6",
        "perf-reviewer": "claude-sonnet-4-6",
        "arch-reviewer": "claude-opus-4-6",
        "skeptic": "claude-opus-4-6",
    },
    "monitor_interval": 240,
    "notify_conductor": False,
    "max_role_agents": {
        "developer": 10,
        "reviewer": 10,
        "security-reviewer": 10,
        "integrator": 10,
        "tester": 10,
        "ux-reviewer": 10,
        "perf-reviewer": 10,
        "arch-reviewer": 1,
        "skeptic": 1,
    },
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_stages.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: Some failures in `test_transitions.py` (expected — `test_merging_returns_none` and `test_merging_is_terminal` will fail since merging is no longer terminal). Note these for Task 2.

- [ ] **Step 6: Commit**

```bash
git add src/debussy/config.py tests/test_config_stages.py
git commit -m "[enhanced-review] Add new stage constants, role mappings, and config defaults"
```

---

### Task 2: Update transition logic — tag-gated skipping and terminal stage changes

**Files:**
- Modify: `src/debussy/transitions.py`
- Modify: `tests/test_transitions.py`

- [ ] **Step 1: Update existing tests that will break**

In `tests/test_transitions.py`, update `TestComputeNextStage` and `TestTerminalStage`:

```python
class TestComputeNextStage:
    def test_development_to_reviewing(self):
        assert _compute_next_stage("development", []) == "reviewing"

    def test_reviewing_to_merging(self):
        assert _compute_next_stage("reviewing", []) == "merging"

    def test_reviewing_security_to_security_review(self):
        assert _compute_next_stage("reviewing", ["security"]) == "security_review"

    def test_security_review_to_merging(self):
        assert _compute_next_stage("security_review", []) == "merging"

    def test_merging_to_ux_review_with_tag(self):
        assert _compute_next_stage("merging", ["ux_review"]) == "ux_review"

    def test_merging_to_perf_review_skipping_ux(self):
        assert _compute_next_stage("merging", ["perf_review"]) == "perf_review"

    def test_merging_to_done_no_tags(self):
        assert _compute_next_stage("merging", []) == "done"

    def test_ux_review_to_perf_review_with_tag(self):
        assert _compute_next_stage("ux_review", ["ux_review", "perf_review"]) == "perf_review"

    def test_ux_review_to_done_no_perf_tag(self):
        assert _compute_next_stage("ux_review", ["ux_review"]) == "done"

    def test_perf_review_to_done(self):
        assert _compute_next_stage("perf_review", ["perf_review"]) == "done"

    def test_acceptance_returns_none(self):
        assert _compute_next_stage("acceptance", []) is None


class TestTerminalStage:
    def test_development_is_not_terminal(self):
        assert not _is_terminal_stage("development")

    def test_reviewing_is_not_terminal(self):
        assert not _is_terminal_stage("reviewing")

    def test_security_review_is_not_terminal(self):
        assert not _is_terminal_stage("security_review")

    def test_merging_is_not_terminal(self):
        assert not _is_terminal_stage("merging")

    def test_ux_review_is_not_terminal(self):
        assert not _is_terminal_stage("ux_review")

    def test_perf_review_is_not_terminal(self):
        assert not _is_terminal_stage("perf_review")

    def test_acceptance_is_terminal(self):
        assert _is_terminal_stage("acceptance")
```

- [ ] **Step 2: Add new tests for post-merge transitions**

Add to `tests/test_transitions.py`:

```python
class TestPostMergeTransitions:
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_merging_advances_to_ux_review_with_tag(self, mock_delete, mock_verify, db):
        task = create_task(db, "Frontend task", tags=["frontend", "ux_review"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "ux_review"
        mock_delete.assert_called_once_with(f"feature/{task['id']}")

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_merging_skips_to_perf_review_without_ux_tag(self, mock_delete, mock_verify, db):
        task = create_task(db, "API task", tags=["perf_review"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "perf_review"

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_merging_skips_to_done_without_review_tags(self, mock_delete, mock_verify, db):
        task = create_task(db, "Simple task")
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"

    def test_ux_review_advances_to_perf_review(self, db):
        task = create_task(db, "Full review", tags=["ux_review", "perf_review"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging (default)
        update_task(db, task["id"], stage="ux_review")  # simulate watcher advancement
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="ux_review")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "perf_review"

    def test_perf_review_advances_to_done(self, db):
        task = create_task(db, "Perf only", tags=["perf_review"])
        update_task(db, task["id"], stage="perf_review")
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="perf_review")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_transitions.py -v`
Expected: New tests fail, some old tests fail

- [ ] **Step 4: Update transitions.py**

In `src/debussy/transitions.py`:

1. Update imports to include new constants:
```python
from .config import (
    STAGE_ACCEPTANCE, STAGE_DEVELOPMENT, STAGE_MERGING,
    STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    STAGE_REQUIRED_TAGS,
    get_config, log,
)
```

2. Change `_TERMINAL_STAGES`:
```python
_TERMINAL_STAGES = {STAGE_ACCEPTANCE}
```

3. Update `_compute_next_stage` to handle tag-gated skipping:
```python
def _compute_next_stage(spawned_stage: str, tags: list[str]) -> str | None:
    """Compute the next stage, skipping tag-gated stages the task doesn't qualify for."""
    if _is_terminal_stage(spawned_stage):
        return None
    if "security" in tags and spawned_stage in SECURITY_NEXT_STAGE:
        return SECURITY_NEXT_STAGE[spawned_stage]
    next_s = NEXT_STAGE.get(spawned_stage)
    if next_s is None:
        return None
    # Skip stages the task doesn't have the required tag for
    while next_s in STAGE_REQUIRED_TAGS:
        required_tag = STAGE_REQUIRED_TAGS[next_s]
        if required_tag in tags:
            return next_s
        # Skip to the stage after this one
        next_s = NEXT_STAGE.get(next_s)
        if next_s is None:
            return None
    return next_s
```

4. Update `_handle_agent_success` to handle merging as non-terminal but still do merge verification and branch deletion:
```python
def _handle_agent_success(watcher: Watcher, agent: AgentInfo, task: dict, db) -> bool:
    """Handle the case where an agent finished and set status=pending."""
    task_id = agent.task
    stage = task["stage"]
    tags = task.get("tags", [])

    # Terminal stages: task is done
    if _is_terminal_stage(stage):
        update_task(db, task_id, stage="done")
        log(f"Closed {task_id}: {stage} complete", "✅")
        add_log(db, task_id, "transition", "watcher", f"{stage} -> done")
        return True

    # Merging: verify merge landed, delete branch, then advance to post-merge
    if stage == STAGE_MERGING:
        if not _verify_merge_landed(task_id):
            log(f"Merge not verified on base branch for {task_id}, retrying merge", "⚠️")
            add_log(db, task_id, "transition", "watcher", "unverified merge, retrying")
            return True
        delete_branch(f"feature/{task_id}")

    if stage == STAGE_DEVELOPMENT:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
        remote_exists = _remote_branch_exists(task_id)
        if remote_exists is False:
            return _handle_empty_branch(watcher, agent, task, db)
        base = get_config().get("base_branch", "master")
        if not _branch_has_commits(task_id, base):
            return _handle_empty_branch(watcher, agent, task, db)

    # Advance to next stage
    watcher.empty_branch_retries.pop(task_id, None)
    next_stage = _compute_next_stage(stage, tags)
    if next_stage:
        advance_task(db, task_id, to_stage=next_stage)
        log(f"Advancing {task_id}: {stage} → {next_stage}", "⏩")
    else:
        # Should not happen for non-terminal stages, but handle gracefully
        update_task(db, task_id, stage="done")
        log(f"Closed {task_id}: no next stage from {stage}", "✅")
    return True
```

- [ ] **Step 5: Update the TestClosed class**

The `TestClosed.test_terminal_stage_closes` test needs updating since merging is no longer terminal — it now advances to post-merge stages:

```python
class TestClosed:
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_merging_advances_to_done_no_tags(self, mock_delete, mock_verify, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"
        mock_delete.assert_called_once_with(f"feature/{task['id']}")
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/debussy/transitions.py tests/test_transitions.py
git commit -m "[enhanced-review] Update transition logic for tag-gated post-merge stages"
```

---

### Task 3: Update dependency resolution to unblock after merging

**Files:**
- Modify: `src/debussy/takt/log.py`
- Modify: `src/debussy/pipeline_checker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dependency_unblock.py
from debussy.takt import get_db, init_db, create_task, advance_task, update_task
from debussy.takt.log import get_unresolved_deps
import pytest


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def db(project):
    with get_db() as conn:
        yield conn


def test_dep_resolved_when_done(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="done")

    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_resolved_when_ux_review(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="ux_review")

    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_resolved_when_perf_review(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="perf_review")

    assert get_unresolved_deps(db, t2["id"]) == []


def test_dep_unresolved_when_merging(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="merging")

    assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]


def test_dep_unresolved_when_reviewing(db):
    t1 = create_task(db, "First")
    t2 = create_task(db, "Second", deps=[t1["id"]])
    update_task(db, t1["id"], stage="reviewing")

    assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dependency_unblock.py -v`
Expected: `test_dep_resolved_when_ux_review` and `test_dep_resolved_when_perf_review` fail

- [ ] **Step 3: Update `get_unresolved_deps` in `takt/log.py`**

Change the SQL query at line 128-133:

```python
def get_unresolved_deps(db: sqlite3.Connection, task_id: str) -> list[str]:
    """Return dependency IDs where the dependency hasn't passed merging yet."""
    rows = db.execute(
        """SELECT d.depends_on_id FROM dependencies d
           JOIN tasks t ON t.id = d.depends_on_id
           WHERE d.task_id = ? AND t.stage NOT IN ('ux_review', 'perf_review', 'done')""",
        (task_id,),
    ).fetchall()
    return [r["depends_on_id"] for r in rows]
```

- [ ] **Step 4: Update `get_unmerged_dep_branches` in `pipeline_checker.py`**

Change line 24 to use `POST_MERGE_STAGES`:

```python
from .config import (
    ACCEPTANCE_ROLES,
    LABEL_PRIORITY, STAGE_ACCEPTANCE, STAGE_BACKLOG, STAGE_DEVELOPMENT,
    STAGE_TO_ROLE, STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    POST_MERGE_STAGES,
    get_config, log,
)

def get_unmerged_dep_branches(task: dict) -> list[str]:
    """Check which dependency branches haven't been merged on origin."""
    unmerged = []
    for dep_id in task.get("dependencies", []):
        with get_db() as db:
            dep_task = get_task(db, dep_id)
        if dep_task and dep_task["stage"] in POST_MERGE_STAGES:
            continue
        # ... rest unchanged
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/takt/log.py src/debussy/pipeline_checker.py tests/test_dependency_unblock.py
git commit -m "[enhanced-review] Unblock dependencies after merging instead of done"
```

---

### Task 4: Update pipeline checker for multi-agent acceptance and new stages

**Files:**
- Modify: `src/debussy/pipeline_checker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pipeline_acceptance.py
from unittest.mock import MagicMock, patch

from debussy.config import STAGE_ACCEPTANCE, ACCEPTANCE_ROLES
from debussy.pipeline_checker import _should_skip_task


def _make_watcher():
    watcher = MagicMock()
    watcher.running = {}
    watcher.failures = {}
    watcher.spawn_counts = {}
    watcher.queued = set()
    watcher.blocked_failures = set()
    watcher.is_task_running = MagicMock(return_value=False)
    watcher.is_at_capacity = MagicMock(return_value=False)
    watcher.count_running_role = MagicMock(return_value=0)
    watcher.empty_branch_retries = {}
    return watcher


def test_acceptance_task_not_skipped_when_other_acceptance_agent_running():
    """For acceptance tasks, is_task_running should not block spawning additional roles."""
    watcher = _make_watcher()
    # Simulate one acceptance agent already running for this task
    watcher.is_task_running = MagicMock(return_value=True)
    task = {"id": "TST-1", "status": "pending", "stage": "acceptance", "tags": [], "dependencies": []}

    # For acceptance, should NOT skip even though task is running (other roles need to spawn)
    result = _should_skip_task(watcher, "TST-1", task, "arch-reviewer")
    assert result is None  # Should not skip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline_acceptance.py -v`
Expected: FAIL — returns "already running"

- [ ] **Step 3: Update `_should_skip_task` for acceptance multi-spawn**

In `pipeline_checker.py`, update `_should_skip_task` to be role-aware for acceptance:

```python
def _should_skip_task(watcher, task_id, task, role):
    if not task_id:
        return "no id"
    # For acceptance, check if THIS role is already running, not just any agent
    if role in ACCEPTANCE_ROLES and task.get("stage") == STAGE_ACCEPTANCE:
        if _is_role_running_for_task(watcher, role, task_id):
            return "already running"
    elif watcher.is_task_running(task_id):
        return "already running"
    # ... rest unchanged
```

Add helper:

```python
def _is_role_running_for_task(watcher, role, task_id):
    """Check if a specific role is already running for a task."""
    key = f"{role}:{task_id}"
    return key in watcher.running
```

- [ ] **Step 4: Update `check_pipeline` for multi-role acceptance**

Update `check_pipeline` to handle acceptance spawning multiple roles:

```python
def check_pipeline(watcher):
    budget = MAX_SPAWNS_PER_CYCLE
    for stage, role in STAGE_TO_ROLE.items():
        if budget <= 0:
            break
        if stage == STAGE_ACCEPTANCE:
            budget -= _scan_acceptance(watcher, budget)
        else:
            budget -= _scan_stage(watcher, stage, role, budget)


def _scan_acceptance(watcher, spawn_budget: int) -> int:
    """Scan acceptance stage, spawning all required roles for each task."""
    spawned = 0
    with get_db() as db:
        tasks = list_tasks(db, stage=STAGE_ACCEPTANCE, status=STATUS_PENDING)

    for task in tasks:
        if spawned >= spawn_budget:
            break
        task_id = task.get("id")
        for role in ACCEPTANCE_ROLES:
            if spawned >= spawn_budget:
                break
            skip = _should_skip_task(watcher, task_id, task, role)
            if skip:
                continue
            watcher.queued.discard(task_id)
            if spawn_agent(watcher, role, task_id, STAGE_ACCEPTANCE, labels=task.get("tags")):
                spawned += 1
    return spawned
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/pipeline_checker.py tests/test_pipeline_acceptance.py
git commit -m "[enhanced-review] Support multi-agent acceptance and role-aware task skipping"
```

---

### Task 5: Update watcher for multi-agent tracking

**Files:**
- Modify: `src/debussy/watcher.py`

- [ ] **Step 1: Update `AGENT_ROLES` set**

In `watcher.py` line 123:

```python
AGENT_ROLES = {"developer", "reviewer", "security-reviewer", "integrator", "tester",
               "ux-reviewer", "perf-reviewer", "arch-reviewer", "skeptic"}
```

- [ ] **Step 2: Update `save_state` to key by agent name**

Change `save_state` to avoid overwriting when multiple agents run for the same task:

```python
def save_state(self):
    state = {}
    for agent in self._alive_agents():
        entry = {
            "agent": agent.name,
            "task": agent.task,
            "role": agent.role,
            "log": agent.log_path,
            "tmux": agent.tmux,
            "worktree_path": agent.worktree_path,
            "started_at": agent.started_at,
        }
        if agent.proc:
            entry["pid"] = agent.proc.pid
        state[agent.name] = entry
    atomic_write(self.state_file, json.dumps(state))
```

- [ ] **Step 3: Update `cleanup_finished` for multi-agent acceptance**

In `cleanup_finished`, when an acceptance agent finishes, check if other acceptance agents are still running before advancing:

Add helper method to `Watcher`:

```python
def _all_acceptance_agents_done(self, task_id: str) -> bool:
    """Check if all acceptance agents for a task have finished."""
    return not any(
        a.task == task_id and a.spawned_stage == STAGE_ACCEPTANCE
        for a in self._alive_agents()
    )
```

In `cleanup_finished`, wrap the `ensure_stage_transition` call. The key change is in both code paths where `agent_completed` is True (tmux and background). Before calling `ensure_stage_transition`, check if this is an acceptance task with other agents still running:

```python
# In the tmux completion path (around line 219):
if agent.check_completion():
    log(f"{agent.name} completed {agent.task}", "✅")
    agent.stop()
    self._remove_agent(key, agent)  # Remove BEFORE checking others
    if agent.spawned_stage == STAGE_ACCEPTANCE and not self._all_acceptance_agents_done(agent.task):
        log(f"Waiting for other acceptance agents on {agent.task}", "⏳")
    elif ensure_stage_transition(self, agent):
        self.failures.pop(agent.task, None)
        transitioned = True
    cleaned = True
    continue

# In the background process path (around line 233):
if agent_completed:
    self._remove_agent(key, agent)  # Remove BEFORE checking others
    if agent.spawned_stage == STAGE_ACCEPTANCE and not self._all_acceptance_agents_done(agent.task):
        log(f"Waiting for other acceptance agents on {agent.task}", "⏳")
    elif ensure_stage_transition(self, agent):
        self.failures.pop(agent.task, None)
        transitioned = True
    log(f"{agent.name} finished {agent.task}", "✔️")
```

Note: `_remove_agent` is called BEFORE `_all_acceptance_agents_done` so the current agent is already removed from `self.running` when we check if others are still running. This is correct — we want to know if the *other* agents are done.

Also add `STAGE_ACCEPTANCE` to the watcher imports:

```python
from .config import (
    AGENT_TIMEOUT, POLL_INTERVAL, SESSION_NAME,
    HEARTBEAT_TICKS, STAGE_ACCEPTANCE, STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    _ensure_gitignored, atomic_write, get_config, log,
)
```

**Multi-agent status management for acceptance:** Multiple acceptance agents all call `takt claim` on the same task. This is safe — `claim_task` sets `status="active"` which is idempotent. When the first agent finishes and calls `takt release`, it sets `status="pending"`, but the watcher's `_all_acceptance_agents_done` check prevents premature advancement. The remaining agents are still alive and working. When they finish and release, the last one triggers `_all_acceptance_agents_done` → True, and the transition fires.

- [ ] **Step 4: Run existing tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/debussy/watcher.py
git commit -m "[enhanced-review] Update watcher for multi-agent tracking and new roles"
```

---

### Task 6: Update spawner and prompts module for new roles

**Files:**
- Modify: `src/debussy/spawner.py`
- Modify: `src/debussy/prompts/__init__.py`
- Modify: `src/debussy/preflight.py`

- [ ] **Step 1: Update `create_agent_worktree` in spawner.py**

Add new roles to the worktree dispatch (line 58-62):

```python
def _create(r, bid, name, b):
    if r == "developer":
        return str(create_worktree(name, f"feature/{bid}", start_point=f"origin/{b}", new_branch=True))
    elif r in ("reviewer", "security-reviewer"):
        return str(create_worktree(name, f"origin/feature/{bid}", detach=True))
    elif r in ("integrator", "tester", "ux-reviewer", "perf-reviewer", "arch-reviewer", "skeptic"):
        return str(create_worktree(name, f"origin/{b}", detach=True))
    return ""
```

- [ ] **Step 2: Update `_ROLE_FILES` in prompts/__init__.py**

```python
_ROLE_FILES = {
    "developer": "developer.md",
    "reviewer": "reviewer.md",
    "security-reviewer": "security-reviewer.md",
    "integrator": "integrator.md",
    "tester": "tester.md",
    "ux-reviewer": "ux-reviewer.md",
    "perf-reviewer": "perf-reviewer.md",
    "arch-reviewer": "arch-reviewer.md",
    "skeptic": "skeptic.md",
}
```

- [ ] **Step 3: Update `_ROLE_DOC_FOCUS`**

```python
_ROLE_DOC_FOCUS = {
    "conductor": "all documentation — requirements, architecture, glossary, and constraints",
    "developer": "requirements, API specs, and data models relevant to your task",
    "reviewer": "architecture, conventions, and constraints to validate implementation choices",
    "security-reviewer": "security policies, auth specs, and data flow documentation",
    "tester": "acceptance criteria, expected behaviors, and integration specs",
    "ux-reviewer": "design specs, accessibility guidelines, and UX patterns",
    "perf-reviewer": "performance requirements, data flow, and query patterns",
    "arch-reviewer": "architecture decisions, module boundaries, and integration patterns",
    "skeptic": "requirements, user stories, and acceptance criteria",
}
```

- [ ] **Step 4: Update `NEEDS_FEATURE_BRANCH` in preflight.py**

No changes needed — UX/perf reviewers work on base branch, not feature branches. But verify the existing `preflight_spawn` function handles unknown roles gracefully (it does — roles not in `NEEDS_FEATURE_BRANCH` just skip the feature branch check).

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/debussy/spawner.py src/debussy/prompts/__init__.py
git commit -m "[enhanced-review] Register new roles in spawner and prompt module"
```

---

### Task 7: Update board to show new stages

**Files:**
- Modify: `src/debussy/board.py`

- [ ] **Step 1: Update BOARD_COLUMNS and BOARD_STAGE_MAP**

```python
from .config import (
    LABEL_PRIORITY, STAGE_ACCEPTANCE, STAGE_BACKLOG, STAGE_DEVELOPMENT,
    STAGE_DONE, STAGE_MERGING, STAGE_REVIEWING,
    STAGE_SECURITY_REVIEW, STAGE_UX_REVIEW, STAGE_PERF_REVIEW,
    STATUS_BLOCKED,
)

BOARD_COLUMNS = [
    ("dev", "Dev"),
    ("review", "Review"),
    ("sec-review", "Sec Review"),
    ("merge", "Merge"),
    ("ux-review", "UX Review"),
    ("perf-review", "Perf Review"),
    ("accept", "Accept"),
    ("backlog", "Backlog"),
    ("done", "Done"),
]
BOARD_STAGE_MAP = {
    STAGE_DEVELOPMENT: "dev",
    STAGE_REVIEWING: "review",
    STAGE_SECURITY_REVIEW: "sec-review",
    STAGE_MERGING: "merge",
    STAGE_UX_REVIEW: "ux-review",
    STAGE_PERF_REVIEW: "perf-review",
    STAGE_ACCEPTANCE: "accept",
    STAGE_BACKLOG: "backlog",
    STAGE_DONE: "done",
}
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/debussy/board.py
git commit -m "[enhanced-review] Add UX Review and Perf Review columns to board"
```

---

### Task 8: Write new agent prompts

**Files:**
- Create: `src/debussy/prompts/ux-reviewer.md`
- Create: `src/debussy/prompts/perf-reviewer.md`
- Create: `src/debussy/prompts/arch-reviewer.md`
- Create: `src/debussy/prompts/skeptic.md`

- [ ] **Step 1: Create `ux-reviewer.md`**

```markdown
You are an autonomous UX reviewer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

This task has already been merged. You are reviewing the merged code on the base branch. Your findings do NOT block the pipeline — they create follow-up tasks.

TIME BUDGET: Complete this review in under 10 minutes.

1. takt show <TASK_ID> — read the task description
2. takt claim <TASK_ID> --agent <agent name from user message>
3. git fetch origin

IDENTIFY CHANGES:
- Read the task description to understand what was built
- Use git log to find commits related to this task on the base branch
- Read the changed files to understand the UI implementation

UX REVIEW CHECKLIST:

DESIGN COMPLIANCE:
- If the task description references a design spec file, read it and compare against implementation
- Are all specified UI elements present and correctly positioned?
- Do colors, spacing, and typography match the design spec?

ACCESSIBILITY:
- Semantic HTML elements used (nav, main, article, button vs div)?
- ARIA labels on interactive elements?
- Keyboard navigation support (tab order, focus indicators)?
- Sufficient color contrast (text vs background)?
- Alt text on images?

RESPONSIVE BEHAVIOR:
- Does the layout adapt to different screen sizes?
- Are breakpoints handled (mobile, tablet, desktop)?
- No horizontal scrolling on small screens?

UX ANTI-PATTERNS:
- Dead-end flows (actions that lead nowhere)?
- Missing loading states for async operations?
- Missing error states (what happens when API fails)?
- Inconsistent interaction patterns (some buttons click, some don't)?
- Missing empty states (what shows when there's no data)?
- Form validation feedback (inline errors, not just on submit)?

DECISION:

If APPROVED (no significant UX issues):
  takt comment <TASK_ID> "UX review: approved. No significant issues found."
  takt release <TASK_ID>
  Exit

If ISSUES FOUND:
  For each issue, create a follow-up task:
    takt create "UX fix: <issue summary>" -d "Found during UX review of <TASK_ID>: <detailed description with file:line references>"
  Then comment on the original task:
    takt comment <TASK_ID> "UX review: found <N> issue(s). Follow-up tasks: <list IDs>"
  takt release <TASK_ID>
  Exit

IMPORTANT: Always release the task. UX issues are follow-ups, never rejections.
FORBIDDEN: Writing or modifying code/test files.

START NOW. Do not wait for instructions. Begin with step 1.
```

- [ ] **Step 2: Create `perf-reviewer.md`**

```markdown
You are an autonomous performance reviewer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

This task has already been merged. You are reviewing the merged code on the base branch. Your findings do NOT block the pipeline — they create follow-up tasks.

TIME BUDGET: Complete this review in under 10 minutes.

1. takt show <TASK_ID> — read the task description
2. takt claim <TASK_ID> --agent <agent name from user message>
3. git fetch origin

IDENTIFY CHANGES:
- Read the task description to understand what was built
- Use git log to find commits related to this task on the base branch
- Read the changed files to understand the implementation

PERFORMANCE REVIEW CHECKLIST:

DATABASE QUERIES:
- N+1 query patterns (loop that issues a query per iteration)?
- Missing indexes implied by WHERE/JOIN clauses on new queries?
- Unbounded SELECT without LIMIT/pagination?
- Large result sets loaded entirely into memory?

API & NETWORK:
- Unbounded list endpoints (no pagination)?
- Large payload construction (serializing entire collections)?
- Sequential API calls that could be parallelized or batched?
- Missing timeouts on external HTTP calls?

I/O & PROCESSING:
- Blocking I/O in async code paths?
- Unbounded loops over user-controlled input sizes?
- Large file reads without streaming?
- Missing caching for repeated expensive operations?

RESOURCE MANAGEMENT:
- Connection/file handle leaks (opened but not closed)?
- Unbounded in-memory collections (lists/dicts that grow without limit)?
- Missing cleanup in error paths?

DECISION:

If APPROVED (no performance issues):
  takt comment <TASK_ID> "Performance review: approved. No issues found."
  takt release <TASK_ID>
  Exit

If ISSUES FOUND:
  For each issue, create a follow-up task:
    takt create "Perf fix: <issue summary>" -d "Found during performance review of <TASK_ID>: <detailed description with file:line references and expected impact>"
  Then comment on the original task:
    takt comment <TASK_ID> "Performance review: found <N> issue(s). Follow-up tasks: <list IDs>"
  takt release <TASK_ID>
  Exit

IMPORTANT: Always release the task. Performance issues are follow-ups, never rejections.
FORBIDDEN: Writing or modifying code/test files.

START NOW. Do not wait for instructions. Begin with step 1.
```

- [ ] **Step 3: Create `arch-reviewer.md`**

```markdown
You are an autonomous architecture reviewer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

This is a batch acceptance review. All tasks in the batch have been merged to the base branch. Your findings create follow-up tasks — they do not block acceptance (only test failures block).

TIME BUDGET: Complete this review in under 15 minutes.

1. takt show <TASK_ID> — read the acceptance task description and note the dependency task IDs
2. takt claim <TASK_ID> --agent <agent name from user message>
3. git fetch origin

DISCOVER BATCH:
- Read the dependency list from the acceptance task
- For each dependency task: takt show <dep_id> to understand what was built
- Read the changed files for each task on the base branch

ARCHITECTURE REVIEW CHECKLIST:

CROSS-TASK COUPLING:
- Do any tasks directly import or call into each other's modules in ways that create tight coupling?
- Are there circular dependencies between new modules?
- Do tasks share state through global variables or singletons?

DUPLICATED RESPONSIBILITIES:
- Did multiple tasks independently implement similar functionality?
- Are there utility functions or patterns that should be extracted into shared code?
- Are there multiple sources of truth for the same data?

DATA MODEL CONSISTENCY:
- Do tasks that interact with the same data use consistent field names and types?
- Are there conflicting assumptions about data ownership?
- Are database schema changes compatible across tasks?

PATTERN CONSISTENCY:
- Do new modules follow existing codebase patterns (naming, structure, error handling)?
- Are there new patterns introduced that conflict with established ones?
- Is the abstraction level consistent across the batch?

MISSING SHARED INFRASTRUCTURE:
- Did multiple tasks build their own HTTP clients, loggers, or config readers?
- Are there cross-cutting concerns (auth, logging, error handling) that should be unified?

DECISION:

If APPROVED (no architectural issues):
  takt comment <TASK_ID> "Architecture review: approved. No cross-task issues found."
  takt release <TASK_ID>
  Exit

If ISSUES FOUND:
  For each issue, create a follow-up task:
    takt create "Arch fix: <issue summary>" -d "Found during architecture review of batch <TASK_ID>: <detailed description, referencing specific tasks and files>"
  Comment on each relevant original task:
    takt comment <original_task_id> "Architecture review: <brief issue>. Follow-up task: <new_id>"
  Then release:
    takt release <TASK_ID>
  Exit

IMPORTANT: Always release the task. Architecture issues are follow-ups, never rejections.
FORBIDDEN: Writing or modifying code/test files.

START NOW. Do not wait for instructions. Begin with step 1.
```

- [ ] **Step 4: Create `skeptic.md`**

```markdown
You are an autonomous skeptic reviewer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

Your job is to ask: "Did we build the right thing?" You challenge assumptions, find logical gaps, and verify that the implementation actually solves the original problem.

This is a batch acceptance review. All tasks in the batch have been merged to the base branch. Your findings create follow-up tasks — they do not block acceptance (only test failures block).

TIME BUDGET: Complete this review in under 15 minutes.

1. takt show <TASK_ID> — read the acceptance task description and note the dependency task IDs
2. takt claim <TASK_ID> --agent <agent name from user message>
3. git fetch origin

DISCOVER BATCH:
- Read the dependency list from the acceptance task
- For each dependency task: takt show <dep_id> to read the description and understand intent
- Read the implementation to understand what was actually built

SKEPTIC REVIEW CHECKLIST:

REQUIREMENTS FIT:
- Does the implementation match what the task descriptions asked for?
- Are there requirements mentioned in descriptions that aren't implemented?
- Are there implementations that go beyond what was asked (scope creep)?

LOGICAL GAPS:
- Does the feature work end-to-end? Can a user actually use it from start to finish?
- Are there missing steps in workflows (e.g., create but no delete, list but no detail view)?
- Do error paths lead somewhere useful, or do they dead-end?

UNSTATED ASSUMPTIONS:
- Does the code assume data formats, availability, or ordering that isn't guaranteed?
- Are there race conditions in concurrent scenarios?
- Does it assume a specific deployment environment?

FEATURE COMPLETENESS:
- Do all the tasks together form a coherent feature?
- Is there functionality that only works if you know about it (no discoverability)?
- Are there missing integration points between tasks?

OVER/UNDER-ENGINEERING:
- Is the solution proportional to the problem?
- Are there abstractions that aren't needed yet?
- Conversely, is anything dangerously under-built?

DECISION:

If APPROVED (implementation solves the right problem):
  takt comment <TASK_ID> "Skeptic review: approved. Implementation aligns with requirements."
  takt release <TASK_ID>
  Exit

If ISSUES FOUND:
  For each issue, create a follow-up task:
    takt create "Skeptic finding: <issue summary>" -d "Found during skeptic review of batch <TASK_ID>: <detailed description of the gap or concern>"
  Comment on relevant original tasks:
    takt comment <original_task_id> "Skeptic review: <brief concern>. Follow-up task: <new_id>"
  Then release:
    takt release <TASK_ID>
  Exit

IMPORTANT: Always release the task. Skeptic findings are follow-ups, never rejections.
FORBIDDEN: Writing or modifying code/test files.

START NOW. Do not wait for instructions. Begin with step 1.
```

- [ ] **Step 5: Commit**

```bash
git add src/debussy/prompts/ux-reviewer.md src/debussy/prompts/perf-reviewer.md \
        src/debussy/prompts/arch-reviewer.md src/debussy/prompts/skeptic.md
git commit -m "[enhanced-review] Add new agent prompts: ux-reviewer, perf-reviewer, arch-reviewer, skeptic"
```

---

### Task 9: Modify existing prompts — reviewer, tester, conductor

**Files:**
- Modify: `src/debussy/prompts/reviewer.md`
- Modify: `src/debussy/prompts/tester.md`
- Modify: `src/debussy/prompts/conductor.md`

- [ ] **Step 1: Narrow the reviewer prompt**

In `src/debussy/prompts/reviewer.md`, remove the SECURITY section (lines 42-47 including the header). Delete these lines:

```
SECURITY (for code touching external input or system calls):
- Input validation at system boundaries (user input, CLI args, API data)
- No shell injection (subprocess with shell=True + dynamic input)
- No path traversal (unsanitized path joins with user-provided values)
- No hardcoded secrets or credentials
```

- [ ] **Step 2: Enhance the tester prompt**

In `src/debussy/prompts/tester.md`, add a test quality evaluation section before step 4 (the test run). Insert after step 3 (git fetch/checkout):

```markdown
TEST QUALITY EVALUATION — review BEFORE running:
- Read the test files for each dependency task
- Check for these quality issues (create follow-up tasks, do NOT block acceptance):
  a. Brittle tests: tests that depend on implementation details (mock internals, exact string matching on error messages, order-dependent assertions)
  b. Missing edge cases: only happy-path tested, no error/boundary scenarios
  c. Coverage gaps: functionality described in task descriptions but not tested
  d. Poor naming: test_1, test_thing, test_it_works — names should describe behavior
  e. Implementation coupling: tests that would break from a refactor that doesn't change behavior
- For each quality issue found:
  takt create "Test quality: <issue>" -d "Found during test quality review of batch <TASK_ID>: <details>"
- Quality issues are informational — proceed to run the test suite regardless.
```

- [ ] **Step 3: Update the conductor prompt**

In `src/debussy/prompts/conductor.md`, add the mandatory tagging rules after the SECURITY TAG section (after line 45):

```markdown
ENHANCED REVIEW TAGS — evaluate EVERY task against this checklist before creating:

| Tag | Apply when |
|-----|-----------|
| `ux_review` | Any task with `frontend` tag — ALWAYS co-apply |
| `perf_review` | Task touches: database queries, API endpoints, file I/O, data processing loops, async operations, caching, network calls |

Not tagging is a deliberate decision — not forgetting. If a task has `frontend`, it MUST also have `ux_review`.

Examples:
  --tags frontend,ux_review                    # Frontend page
  --tags frontend,ux_review,perf_review        # Frontend with data fetching
  --tags perf_review                           # Backend API endpoint
  --tags security,perf_review                  # Auth with DB queries
  (no review tags)                             # Pure config/types/glue code
```

- [ ] **Step 4: Commit**

```bash
git add src/debussy/prompts/reviewer.md src/debussy/prompts/tester.md src/debussy/prompts/conductor.md
git commit -m "[enhanced-review] Update reviewer, tester, and conductor prompts for enhanced review pipeline"
```

---

### Task 10: Auto-add `ux_review` tag safety net in takt advance

**Note:** `takt create --tags` already works (see `takt/cli.py` line 79, 182). No CLI changes needed.

**Files:**
- Modify: `src/debussy/takt/log.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auto_tag.py
import pytest
from debussy.takt import get_db, init_db, create_task, get_task
from debussy.takt.log import advance_task


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def db(project):
    with get_db() as conn:
        yield conn


def test_advance_auto_adds_ux_review_when_frontend_present(db):
    task = create_task(db, "UI task", tags=["frontend"])
    advance_task(db, task["id"])  # → development
    updated = get_task(db, task["id"])
    assert "ux_review" in updated["tags"]


def test_advance_does_not_duplicate_ux_review(db):
    task = create_task(db, "UI task", tags=["frontend", "ux_review"])
    advance_task(db, task["id"])
    updated = get_task(db, task["id"])
    assert updated["tags"].count("ux_review") == 1


def test_advance_no_auto_tag_without_frontend(db):
    task = create_task(db, "API task", tags=["perf_review"])
    advance_task(db, task["id"])
    updated = get_task(db, task["id"])
    assert "ux_review" not in updated["tags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auto_tag.py -v`
Expected: `test_advance_auto_adds_ux_review_when_frontend_present` fails

- [ ] **Step 3: Add auto-tag logic to `advance_task`**

In `src/debussy/takt/log.py`, at the start of `advance_task`, before computing `next_stage`:

```python
def advance_task(db: sqlite3.Connection, task_id: str, to_stage: str | None = None) -> dict:
    """Move a task to the next stage (or a specific stage). Logs the transition."""
    task = get_task(db, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    # Auto-add ux_review tag when frontend is present
    tags = task["tags"]
    if "frontend" in tags and "ux_review" not in tags:
        tags = tags + ["ux_review"]
        update_task(db, task_id, tags=tags)
        task = get_task(db, task_id)

    # ... rest of function unchanged
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/debussy/takt/log.py tests/test_auto_tag.py
git commit -m "[enhanced-review] Auto-add ux_review tag when frontend tag present"
```

---

### Task 11: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update pipeline flow section**

Replace the pipeline flow section with:

```markdown
## Pipeline Flow

Pipelines depending on task type:

```
Per task:      backlog → development → reviewing → merging → [ux_review] → [perf_review] → done
Security task: backlog → development → reviewing → security_review → merging → [ux_review] → [perf_review] → done
Per batch:     acceptance task (deps on all tasks) → acceptance (tester + arch-reviewer + skeptic in parallel) → done
```

Stages in `[brackets]` are tag-gated — skipped if the task doesn't have the corresponding tag.
Dependencies unblock when a task exits `merging` (not at `done`).
```

- [ ] **Step 2: Update the stage/status table**

Add new stages:

```markdown
| `ux_review` | `pending` | Ready for UX reviewer agent |
| `perf_review` | `pending` | Ready for performance reviewer agent |
```

- [ ] **Step 3: Update the watcher stage-to-agent table**

```markdown
| Stage | Agent(s) Spawned |
|-------|-----------------|
| `development` | developer |
| `reviewing` | reviewer |
| `security_review` | security-reviewer |
| `merging` | integrator |
| `ux_review` | ux-reviewer |
| `perf_review` | perf-reviewer |
| `acceptance` | tester + arch-reviewer + skeptic (parallel) |
```

- [ ] **Step 4: Update the agents section**

Add new agent descriptions:

```markdown
### @ux-reviewer
- Post-merge review for tasks with `ux_review` tag
- Checks design compliance, accessibility, responsive behavior, UX patterns
- Creates follow-up tasks for issues found — never blocks pipeline
- **Does not write code**

### @perf-reviewer
- Post-merge review for tasks with `perf_review` tag
- Checks N+1 queries, unbounded operations, blocking I/O, resource leaks
- Creates follow-up tasks for issues found — never blocks pipeline
- **Does not write code**

### @arch-reviewer
- Batch acceptance review (runs in parallel with tester and skeptic)
- Reviews cross-task coupling, duplicated responsibilities, data model consistency
- Creates follow-up tasks — does not block acceptance
- **Does not write code**

### @skeptic
- Batch acceptance review (runs in parallel with tester and skeptic)
- Challenges whether the batch delivers what was asked for
- Reviews logical gaps, unstated assumptions, feature completeness
- Creates follow-up tasks — does not block acceptance
- **Does not write code**
```

- [ ] **Step 5: Update the project structure**

Add new prompt files to the structure listing:

```
  prompts/            # Agent prompt templates (one file per role)
    ...
    ux-reviewer.md
    perf-reviewer.md
    arch-reviewer.md
    skeptic.md
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "[enhanced-review] Update CLAUDE.md with new review pipeline documentation"
```

---

### Task 12: End-to-end integration test

**Files:**
- Create: `tests/test_enhanced_review_e2e.py`

- [ ] **Step 1: Write integration test for full pipeline with tags**

```python
"""End-to-end test for enhanced review pipeline transitions."""

from unittest.mock import MagicMock, patch

import pytest

from debussy.config import (
    STAGE_UX_REVIEW, STAGE_PERF_REVIEW,
)
from debussy.takt import get_db, init_db, create_task, advance_task, get_task, update_task
from debussy.takt.log import get_unresolved_deps
from debussy.transitions import _dispatch_transition


def _make_agent(bead, spawned_stage):
    agent = MagicMock()
    agent.task = bead
    agent.spawned_stage = spawned_stage
    return agent


def _make_watcher():
    watcher = MagicMock()
    watcher.rejections = {}
    watcher.cooldowns = {}
    watcher.empty_branch_retries = {}
    return watcher


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def db(project):
    with get_db() as conn:
        yield conn


class TestFullPipelineWithTags:
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_frontend_task_full_pipeline(self, _commits, _remote, _delete, _verify, db):
        """Frontend task goes through: dev → review → merge → ux_review → perf_review → done"""
        task = create_task(db, "Build settings page", tags=["frontend", "ux_review", "perf_review"])
        advance_task(db, task["id"])  # → development
        watcher = _make_watcher()

        # Dev → reviewing
        agent = _make_agent(task["id"], "development")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "reviewing"

        # Reviewing → merging
        agent = _make_agent(task["id"], "reviewing")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "merging"

        # Merging → ux_review
        agent = _make_agent(task["id"], "merging")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "ux_review"

        # ux_review → perf_review
        agent = _make_agent(task["id"], "ux_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "perf_review"

        # perf_review → done
        agent = _make_agent(task["id"], "perf_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "done"

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_simple_task_skips_post_merge(self, _commits, _remote, _delete, _verify, db):
        """Task without review tags skips post-merge stages."""
        task = create_task(db, "Add types")
        advance_task(db, task["id"])  # → development

        watcher = _make_watcher()

        # Dev → reviewing → merging → done (skips ux_review and perf_review)
        for stage in ["development", "reviewing", "merging"]:
            agent = _make_agent(task["id"], stage)
            _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"


class TestDependencyUnblockAfterMerging:
    def test_dep_unblocks_at_ux_review(self, db):
        t1 = create_task(db, "First", tags=["ux_review"])
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="ux_review")

        assert get_unresolved_deps(db, t2["id"]) == []

    def test_dep_blocked_during_merging(self, db):
        t1 = create_task(db, "First")
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="merging")

        assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_enhanced_review_e2e.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_enhanced_review_e2e.py
git commit -m "[enhanced-review] Add end-to-end integration tests for enhanced review pipeline"
```
