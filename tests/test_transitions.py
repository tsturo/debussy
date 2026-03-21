"""Tests for stage transition logic using takt."""

from unittest.mock import MagicMock, patch

import pytest

from debussy.transitions import (
    MAX_RETRIES,
    _compute_next_stage, _dispatch_transition, _handle_agent_success,
    _handle_empty_branch, _is_terminal_stage, _remote_branch_exists,
    ensure_stage_transition,
)
from debussy.takt import get_db, init_db, create_task, advance_task, update_task, get_task
from debussy.takt.log import add_log


def _make_agent(bead="TST-1", spawned_stage="development"):
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


def _make_dev_task(db, task_id=None):
    """Create a task and advance it to development stage."""
    task = create_task(db, "Test task")
    advance_task(db, task["id"])  # → development
    return task


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


class TestDispatchAdvance:
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_development_to_reviewing(self, mock_commits, mock_remote, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        result = _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert result is True
        updated = get_task(db, task["id"])
        assert updated["stage"] == "reviewing"

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_reviewing_to_merging(self, mock_commits, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="reviewing")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "merging"


class TestSecurityRouting:
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_reviewing_routes_to_security_review(self, mock_commits, db):
        task = create_task(db, "Secure task", tags=["security"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="reviewing")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "security_review"

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_security_review_to_merging(self, mock_commits, db):
        task = create_task(db, "Secure task", tags=["security"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → security_review
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="security_review")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "merging"


class TestInProgressReset:
    def test_resets_to_pending(self, db):
        task = _make_dev_task(db)
        update_task(db, task["id"], status="active")
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["status"] == "pending"


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

class TestBlocked:
    def test_blocked_stays(self, db):
        task = _make_dev_task(db)
        update_task(db, task["id"], status="blocked")
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["status"] == "blocked"


class TestExternalRemoval:
    def test_stage_changed_externally(self, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")  # agent thinks development

        result = _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert result is True
        # Stage should remain reviewing (not modified by watcher)
        assert get_task(db, task["id"])["stage"] == "reviewing"


class TestEmptyBranch:
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_retries(self, mock_cfg, mock_commits, mock_remote, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert watcher.empty_branch_retries[task["id"]] == 1
        assert get_task(db, task["id"])["stage"] == "development"

    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_max_retries_blocks(self, mock_cfg, mock_commits, mock_remote, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        watcher.empty_branch_retries[task["id"]] = MAX_RETRIES - 1
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["status"] == "blocked"


class TestRemoteBranchExists:
    @patch("debussy.transitions.subprocess.run")
    def test_returns_true_when_branch_exists(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\trefs/heads/feature/TST-1\n",
        )
        assert _remote_branch_exists("TST-1") is True

    @patch("debussy.transitions.subprocess.run")
    def test_returns_false_when_branch_missing(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert _remote_branch_exists("TST-1") is False

    @patch("debussy.transitions.subprocess.run")
    def test_returns_none_on_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _remote_branch_exists("TST-1") is None

    @patch("debussy.transitions.subprocess.run", side_effect=OSError("network"))
    def test_returns_none_on_exception(self, mock_run):
        assert _remote_branch_exists("TST-1") is None


class TestRemoteBranchGate:
    @patch("debussy.transitions._remote_branch_exists", return_value=False)
    def test_missing_remote_triggers_empty_branch(self, mock_remote, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert watcher.empty_branch_retries[task["id"]] == 1
        assert get_task(db, task["id"])["stage"] == "development"

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions._remote_branch_exists", return_value=None)
    def test_network_failure_skips_remote_check(self, mock_remote, mock_commits, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "reviewing"


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
        advance_task(db, task["id"])  # → merging
        update_task(db, task["id"], stage="ux_review")
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


class TestMergeVerification:
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_verified_merge_closes(self, mock_delete, mock_verify, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"
        mock_delete.assert_called_once()

    @patch("debussy.transitions._verify_merge_landed", return_value=False)
    def test_unverified_merge_retries(self, mock_verify, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        # Should stay at merging for retry
        assert get_task(db, task["id"])["stage"] == "merging"


class TestEnsureStageTransition:
    """Tests for ensure_stage_transition called directly (not via _dispatch_transition).

    These tests use `project` (not `db`) so connections are closed between operations,
    avoiding WAL write-lock conflicts when ensure_stage_transition opens its own connection.
    """

    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_advances_development_task_to_reviewing(self, mock_commits, mock_remote, project):
        """ensure_stage_transition advances a development task to reviewing when branch has commits."""
        with get_db() as db:
            task = _make_dev_task(db)
            task_id = task["id"]

        watcher = _make_watcher()
        agent = _make_agent(bead=task_id, spawned_stage="development")

        result = ensure_stage_transition(watcher, agent)

        assert result is True
        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["stage"] == "reviewing"

    def test_missing_spawned_stage_returns_true_immediately(self, project):
        """ensure_stage_transition returns True immediately when spawned_stage is None."""
        with get_db() as db:
            task = _make_dev_task(db)
            task_id = task["id"]

        watcher = _make_watcher()
        agent = _make_agent(bead=task_id, spawned_stage=None)

        result = ensure_stage_transition(watcher, agent)

        assert result is True
        # Task should remain unchanged since we returned early
        with get_db() as db:
            updated = get_task(db, task_id)
        assert updated["stage"] == "development"

    def test_nonexistent_task_returns_false(self, project):
        """ensure_stage_transition returns False when the task does not exist."""
        watcher = _make_watcher()
        agent = _make_agent(bead="TST-999", spawned_stage="development")

        result = ensure_stage_transition(watcher, agent)

        assert result is False
