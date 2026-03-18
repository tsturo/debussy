"""Tests for stage transition logic using takt."""

from unittest.mock import MagicMock, patch

import pytest

from debussy.transitions import (
    MAX_REJECTIONS, MAX_RETRIES,
    _compute_next_stage, _dispatch_transition, _handle_agent_success,
    _handle_empty_branch, _is_terminal_stage, handle_rejection,
    ensure_stage_transition,
)
from debussy.takt import get_db, init_db, create_task, advance_task, update_task, get_task
from debussy.takt.log import add_log


def _make_agent(bead="takt-test1", spawned_stage="development"):
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

    def test_merging_returns_none(self):
        assert _compute_next_stage("merging", []) is None

    def test_acceptance_returns_none(self):
        assert _compute_next_stage("acceptance", []) is None


class TestTerminalStage:
    def test_development_is_not_terminal(self):
        assert not _is_terminal_stage("development")

    def test_reviewing_is_not_terminal(self):
        assert not _is_terminal_stage("reviewing")

    def test_security_review_is_not_terminal(self):
        assert not _is_terminal_stage("security_review")

    def test_merging_is_terminal(self):
        assert _is_terminal_stage("merging")

    def test_acceptance_is_terminal(self):
        assert _is_terminal_stage("acceptance")


class TestDispatchAdvance:
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_development_to_reviewing(self, mock_commits, db):
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


class TestRejection:
    def test_rejection_sends_to_development(self, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="reviewing")

        handle_rejection(watcher, agent, db)

        updated = get_task(db, task["id"])
        assert updated["stage"] == "development"
        assert updated["rejection_count"] == 1
        assert watcher.rejections[task["id"]] == 1

    def test_max_rejections_blocks(self, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        # Pre-set 2 rejections
        update_task(db, task["id"], rejection_count=MAX_REJECTIONS - 1)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="reviewing")

        handle_rejection(watcher, agent, db)

        updated = get_task(db, task["id"])
        assert updated["status"] == "blocked"


class TestAcceptanceRejection:
    def test_acceptance_rejection_blocks(self, db):
        task = create_task(db, "Acceptance task")
        advance_task(db, task["id"], to_stage="acceptance")
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="acceptance")

        handle_rejection(watcher, agent, db)

        updated = get_task(db, task["id"])
        assert updated["status"] == "blocked"


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
    def test_terminal_stage_closes(self, mock_delete, mock_verify, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"
        mock_delete.assert_called_once_with(f"feature/{task['id']}")

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    def test_closed_clears_rejections(self, mock_delete, mock_verify, db):
        task = _make_dev_task(db)
        advance_task(db, task["id"])  # → reviewing
        advance_task(db, task["id"])  # → merging
        watcher = _make_watcher()
        watcher.rejections[task["id"]] = 2
        agent = _make_agent(bead=task["id"], spawned_stage="merging")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert task["id"] not in watcher.rejections


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
    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_retries(self, mock_cfg, mock_commits, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert watcher.empty_branch_retries[task["id"]] == 1
        assert get_task(db, task["id"])["stage"] == "development"

    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_max_retries_blocks(self, mock_cfg, mock_commits, db):
        task = _make_dev_task(db)
        watcher = _make_watcher()
        watcher.empty_branch_retries[task["id"]] = MAX_RETRIES - 1
        agent = _make_agent(bead=task["id"], spawned_stage="development")

        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["status"] == "blocked"


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
