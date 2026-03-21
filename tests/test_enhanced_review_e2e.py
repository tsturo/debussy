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
        """Frontend task goes through: dev -> review -> merge -> ux_review -> perf_review -> done"""
        task = create_task(db, "Build settings page", tags=["frontend", "ux_review", "perf_review"])
        advance_task(db, task["id"])  # backlog -> development
        watcher = _make_watcher()

        # Dev -> reviewing
        agent = _make_agent(task["id"], "development")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "reviewing"

        # Reviewing -> merging
        agent = _make_agent(task["id"], "reviewing")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "merging"

        # Merging -> ux_review
        agent = _make_agent(task["id"], "merging")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "ux_review"

        # ux_review -> perf_review
        agent = _make_agent(task["id"], "ux_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "perf_review"

        # perf_review -> done
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
        advance_task(db, task["id"])  # backlog -> development

        watcher = _make_watcher()

        # Dev -> reviewing -> merging -> done (skips ux_review and perf_review)
        for stage in ["development", "reviewing", "merging"]:
            agent = _make_agent(task["id"], stage)
            _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        assert get_task(db, task["id"])["stage"] == "done"

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_perf_only_skips_ux(self, _commits, _remote, _delete, _verify, db):
        """Task with only perf_review tag skips ux_review."""
        task = create_task(db, "API endpoint", tags=["perf_review"])
        advance_task(db, task["id"])

        watcher = _make_watcher()

        for stage in ["development", "reviewing"]:
            agent = _make_agent(task["id"], stage)
            _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)

        # Merging -> perf_review (skips ux_review)
        agent = _make_agent(task["id"], "merging")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "perf_review"

        # perf_review -> done
        agent = _make_agent(task["id"], "perf_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "done"

    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions._remote_branch_exists", return_value=True)
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    def test_security_task_with_reviews(self, _commits, _remote, _delete, _verify, db):
        """Security task goes through security_review before merging, then post-merge reviews."""
        task = create_task(db, "Auth endpoint", tags=["security", "perf_review"])
        advance_task(db, task["id"])

        watcher = _make_watcher()

        # Dev -> reviewing
        agent = _make_agent(task["id"], "development")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "reviewing"

        # Reviewing -> security_review (because of security tag)
        agent = _make_agent(task["id"], "reviewing")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "security_review"

        # security_review -> merging
        agent = _make_agent(task["id"], "security_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "merging"

        # merging -> perf_review (skips ux_review)
        agent = _make_agent(task["id"], "merging")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "perf_review"

        # perf_review -> done
        agent = _make_agent(task["id"], "perf_review")
        _dispatch_transition(watcher, agent, get_task(db, task["id"]), db)
        assert get_task(db, task["id"])["stage"] == "done"


class TestDependencyUnblockAfterMerging:
    def test_dep_unblocks_at_ux_review(self, db):
        t1 = create_task(db, "First", tags=["ux_review"])
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="ux_review")
        assert get_unresolved_deps(db, t2["id"]) == []

    def test_dep_unblocks_at_perf_review(self, db):
        t1 = create_task(db, "First", tags=["perf_review"])
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="perf_review")
        assert get_unresolved_deps(db, t2["id"]) == []

    def test_dep_blocked_during_merging(self, db):
        t1 = create_task(db, "First")
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="merging")
        assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]

    def test_dep_blocked_during_reviewing(self, db):
        t1 = create_task(db, "First")
        t2 = create_task(db, "Second", deps=[t1["id"]])
        update_task(db, t1["id"], stage="reviewing")
        assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]


class TestAutoTagging:
    def test_frontend_auto_gets_ux_review(self, db):
        task = create_task(db, "UI", tags=["frontend"])
        advance_task(db, task["id"])
        assert "ux_review" in get_task(db, task["id"])["tags"]

    def test_no_duplicate_ux_review(self, db):
        task = create_task(db, "UI", tags=["frontend", "ux_review"])
        advance_task(db, task["id"])
        assert get_task(db, task["id"])["tags"].count("ux_review") == 1
