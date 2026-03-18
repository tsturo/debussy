"""Tests for pipeline_checker.py — orphan reset, dep release, and skip logic."""

from unittest.mock import MagicMock, patch

import pytest

from debussy.takt import get_db, init_db, create_task, advance_task, update_task, get_task
from debussy.pipeline_checker import reset_orphaned, release_ready, _should_skip_task
from debussy.config import (
    STAGE_DEVELOPMENT, STAGE_BACKLOG, STAGE_ACCEPTANCE,
    STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _make_watcher(running_tasks=None):
    watcher = MagicMock()
    watcher.running = {}
    if running_tasks:
        for task_id in running_tasks:
            agent = MagicMock()
            agent.task = task_id
            watcher.running[task_id] = agent
    watcher.empty_branch_retries = {}
    watcher.failures = {}
    watcher.spawn_counts = {}
    watcher.blocked_failures = set()
    watcher.queued = set()
    watcher.is_task_running.return_value = False
    watcher.is_at_capacity.return_value = False
    watcher.count_running_role.return_value = 0
    return watcher


# ─── reset_orphaned ────────────────────────────────────────────────────────────

class TestResetOrphaned:
    def test_active_task_with_no_agent_gets_reset(self, project):
        """Active task with no running agent should be reset to pending."""
        with get_db() as db:
            task = create_task(db, "Orphaned task")
            advance_task(db, task["id"])  # → development
            update_task(db, task["id"], status=STATUS_ACTIVE)
            task_id = task["id"]

        watcher = _make_watcher()  # no running tasks

        reset_orphaned(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["status"] == STATUS_PENDING

    def test_active_task_with_running_agent_is_not_reset(self, project):
        """Active task that has a running agent should NOT be reset."""
        with get_db() as db:
            task = create_task(db, "Live task")
            advance_task(db, task["id"])  # → development
            update_task(db, task["id"], status=STATUS_ACTIVE)
            task_id = task["id"]

        watcher = _make_watcher(running_tasks={task_id})

        reset_orphaned(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["status"] == STATUS_ACTIVE

    def test_active_task_in_unmanaged_stage_is_skipped(self, project):
        """Active task in a stage not managed by watcher (e.g. 'done') is skipped."""
        with get_db() as db:
            task = create_task(db, "Done task")
            update_task(db, task["id"], stage="done", status=STATUS_ACTIVE)
            task_id = task["id"]

        watcher = _make_watcher()

        reset_orphaned(watcher)

        # Should not have been reset — stage 'done' is not in STAGE_TO_ROLE
        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["status"] == STATUS_ACTIVE


# ─── release_ready ─────────────────────────────────────────────────────────────

class TestReleaseReady:
    def test_blocked_task_with_resolved_deps_gets_unblocked(self, project):
        """Blocked task whose deps are all done should be set back to pending."""
        with get_db() as db:
            dep = create_task(db, "Dependency")
            update_task(db, dep["id"], stage="done")
            task = create_task(db, "Blocked task", deps=[dep["id"]])
            advance_task(db, task["id"])  # → development
            update_task(db, task["id"], status=STATUS_BLOCKED)
            task_id = task["id"]

        watcher = _make_watcher()

        release_ready(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["status"] == STATUS_PENDING

    def test_backlog_task_with_resolved_deps_gets_advanced(self, project):
        """Backlog task whose deps are all done should be advanced to development."""
        with get_db() as db:
            dep = create_task(db, "Dependency")
            update_task(db, dep["id"], stage="done")
            task = create_task(db, "Backlog task", deps=[dep["id"]])
            # Task starts in backlog by default
            task_id = task["id"]

        watcher = _make_watcher()

        release_ready(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["stage"] == STAGE_DEVELOPMENT

    def test_task_with_unresolved_deps_is_not_released(self, project):
        """Task whose dep is still in development should NOT be released."""
        with get_db() as db:
            dep = create_task(db, "Unfinished dep")
            advance_task(db, dep["id"])  # → development, not done
            task = create_task(db, "Waiting task", deps=[dep["id"]])
            # Task starts in backlog
            task_id = task["id"]

        watcher = _make_watcher()

        release_ready(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        # Should remain in backlog (not advanced)
        assert updated["stage"] == STAGE_BACKLOG

    def test_blocked_acceptance_task_is_not_released(self, project):
        """Blocked acceptance task should NOT be unblocked by release_ready."""
        with get_db() as db:
            dep = create_task(db, "Done dep")
            update_task(db, dep["id"], stage="done")
            task = create_task(db, "Acceptance task", deps=[dep["id"]])
            advance_task(db, task["id"], to_stage=STAGE_ACCEPTANCE)
            update_task(db, task["id"], status=STATUS_BLOCKED)
            task_id = task["id"]

        watcher = _make_watcher()

        release_ready(watcher)

        with get_db() as db:
            updated = get_task(db, task_id)
        # Should remain blocked — acceptance tasks are exempted
        assert updated["status"] == STATUS_BLOCKED


# ─── _should_skip_task ─────────────────────────────────────────────────────────

class TestShouldSkipTask:
    def test_returns_already_running_if_task_is_running(self, project):
        """Should skip with 'already running' when agent is running for the task."""
        with get_db() as db:
            task = create_task(db, "Running task")
            advance_task(db, task["id"])
            task_id = task["id"]
            task_dict = get_task(db, task_id)

        watcher = _make_watcher()
        watcher.is_task_running.return_value = True

        result = _should_skip_task(watcher, task_id, task_dict, "developer")
        assert result == "already running"

    def test_returns_blocked_if_task_status_is_blocked(self, project):
        """Should skip with 'blocked' when task status is blocked."""
        with get_db() as db:
            task = create_task(db, "Blocked task")
            advance_task(db, task["id"])
            update_task(db, task["id"], status=STATUS_BLOCKED)
            task_id = task["id"]
            task_dict = get_task(db, task_id)

        watcher = _make_watcher()
        watcher.is_task_running.return_value = False

        result = _should_skip_task(watcher, task_id, task_dict, "developer")
        assert result == "blocked"

    def test_returns_unresolved_deps_if_deps_not_done(self, project):
        """Should skip with 'unresolved deps' when dependency is not done."""
        with get_db() as db:
            dep = create_task(db, "Pending dep")
            advance_task(db, dep["id"])  # → development, not done
            task = create_task(db, "Task with dep", deps=[dep["id"]])
            advance_task(db, task["id"])
            task_id = task["id"]
            task_dict = get_task(db, task_id)

        watcher = _make_watcher()
        watcher.is_task_running.return_value = False

        result = _should_skip_task(watcher, task_id, task_dict, "developer")
        assert result == "unresolved deps"

    def test_returns_none_if_all_checks_pass(self, project):
        """Should return None (no skip) when all conditions are satisfied."""
        with get_db() as db:
            task = create_task(db, "Ready task")
            advance_task(db, task["id"])
            task_id = task["id"]
            task_dict = get_task(db, task_id)

        watcher = _make_watcher()
        watcher.is_task_running.return_value = False
        watcher.is_at_capacity.return_value = False
        watcher.count_running_role.return_value = 0

        with patch("debussy.pipeline_checker.get_config", return_value={"max_role_agents": {}}):
            result = _should_skip_task(watcher, task_id, task_dict, "developer")

        assert result is None
