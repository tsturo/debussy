"""Tests for takt log and workflow operations."""

import pytest

from debussy.takt.db import get_db
from debussy.takt.models import create_task, get_task, update_task
from debussy.takt.log import (
    add_comment,
    add_log,
    get_log,
    advance_task,
    reject_task,
    claim_task,
    release_task,
    block_task,
    get_unresolved_deps,
)


@pytest.fixture
def db(tmp_path):
    with get_db(tmp_path) as conn:
        yield conn


def _make_task(db, title="Test", **kwargs):
    return create_task(db, title, **kwargs)


class TestLogOperations:
    def test_add_comment(self, db):
        task = _make_task(db)
        add_comment(db, task["id"], "dev", "Looks good")
        entries = get_log(db, task["id"])
        assert len(entries) == 1
        assert entries[0]["type"] == "comment"
        assert entries[0]["author"] == "dev"
        assert entries[0]["message"] == "Looks good"

    def test_add_log_generic(self, db):
        task = _make_task(db)
        add_log(db, task["id"], "transition", "system", "stage change")
        entries = get_log(db, task["id"])
        assert len(entries) == 1
        assert entries[0]["type"] == "transition"

    def test_get_log_filter_by_type(self, db):
        task = _make_task(db)
        add_comment(db, task["id"], "dev", "comment1")
        add_log(db, task["id"], "transition", "system", "moved")
        add_comment(db, task["id"], "dev", "comment2")
        comments = get_log(db, task["id"], type="comment")
        assert len(comments) == 2
        transitions = get_log(db, task["id"], type="transition")
        assert len(transitions) == 1
        all_entries = get_log(db, task["id"])
        assert len(all_entries) == 3

    def test_get_log_ordered(self, db):
        task = _make_task(db)
        add_comment(db, task["id"], "a", "first")
        add_comment(db, task["id"], "b", "second")
        entries = get_log(db, task["id"])
        assert entries[0]["message"] == "first"
        assert entries[1]["message"] == "second"


class TestAdvanceTask:
    def test_backlog_to_development(self, db):
        task = _make_task(db)
        result = advance_task(db, task["id"])
        assert result["stage"] == "development"
        assert result["status"] == "pending"

    def test_development_to_reviewing(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])  # -> development
        result = advance_task(db, task["id"])
        assert result["stage"] == "reviewing"

    def test_reviewing_to_merging(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])  # -> development
        advance_task(db, task["id"])  # -> reviewing
        result = advance_task(db, task["id"])
        assert result["stage"] == "merging"

    def test_merging_to_done(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])  # -> development
        advance_task(db, task["id"])  # -> reviewing
        advance_task(db, task["id"])  # -> merging
        result = advance_task(db, task["id"])
        assert result["stage"] == "done"

    def test_full_pipeline(self, db):
        task = _make_task(db)
        stages = []
        for _ in range(4):
            task = advance_task(db, task["id"])
            stages.append(task["stage"])
        assert stages == ["development", "reviewing", "merging", "done"]

    def test_security_routing(self, db):
        task = _make_task(db, tags=["security"])
        advance_task(db, task["id"])  # -> development
        advance_task(db, task["id"])  # -> reviewing
        result = advance_task(db, task["id"])  # -> security_review (not merging)
        assert result["stage"] == "security_review"
        result = advance_task(db, task["id"])  # -> merging
        assert result["stage"] == "merging"

    def test_explicit_to_stage(self, db):
        task = _make_task(db)
        result = advance_task(db, task["id"], to_stage="reviewing")
        assert result["stage"] == "reviewing"

    def test_logs_transition(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])
        entries = get_log(db, task["id"], type="transition")
        assert len(entries) == 1
        assert "backlog -> development" in entries[0]["message"]

    def test_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="Task not found"):
            advance_task(db, "XXX-999")

    def test_acceptance_to_done(self, db):
        task = _make_task(db)
        advance_task(db, task["id"], to_stage="acceptance")
        result = advance_task(db, task["id"])
        assert result["stage"] == "done"


class TestRejectTask:
    def test_returns_to_development(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])  # -> development
        advance_task(db, task["id"])  # -> reviewing
        result = reject_task(db, task["id"])
        assert result["stage"] == "development"
        assert result["status"] == "pending"
        assert result["rejection_count"] == 1

    def test_increments_counter(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])  # -> development
        advance_task(db, task["id"])  # -> reviewing
        reject_task(db, task["id"])
        assert get_task(db, task["id"])["rejection_count"] == 1
        advance_task(db, task["id"])  # -> reviewing again
        reject_task(db, task["id"])
        assert get_task(db, task["id"])["rejection_count"] == 2

    def test_blocks_after_three(self, db):
        task = _make_task(db)
        for _ in range(3):
            advance_task(db, task["id"])  # -> development
            advance_task(db, task["id"])  # -> reviewing
            task = reject_task(db, task["id"])
        assert task["status"] == "blocked"
        assert task["rejection_count"] == 3

    def test_logs_rejection(self, db):
        task = _make_task(db)
        advance_task(db, task["id"])
        reject_task(db, task["id"], author="reviewer")
        entries = get_log(db, task["id"], type="transition")
        assert any("rejected" in e["message"] for e in entries)

    def test_acceptance_blocks_instead_of_development(self, db):
        task = _make_task(db)
        advance_task(db, task["id"], to_stage="acceptance")
        result = reject_task(db, task["id"])
        assert result["stage"] == "acceptance"
        assert result["status"] == "blocked"
        assert result["rejection_count"] == 1

    def test_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="Task not found"):
            reject_task(db, "XXX-999")


class TestClaimTask:
    def test_sets_active(self, db):
        task = _make_task(db)
        result = claim_task(db, task["id"], "developer-1")
        assert result["status"] == "active"

    def test_logs_assignment(self, db):
        task = _make_task(db)
        claim_task(db, task["id"], "developer-1")
        entries = get_log(db, task["id"], type="assignment")
        assert len(entries) == 1
        assert entries[0]["author"] == "developer-1"


class TestReleaseTask:
    def test_sets_pending(self, db):
        task = _make_task(db)
        claim_task(db, task["id"], "dev")
        result = release_task(db, task["id"])
        assert result["status"] == "pending"

    def test_logs_release(self, db):
        task = _make_task(db)
        release_task(db, task["id"])
        entries = get_log(db, task["id"], type="transition")
        assert any("released" in e["message"] for e in entries)


class TestBlockTask:
    def test_sets_blocked(self, db):
        task = _make_task(db)
        result = block_task(db, task["id"])
        assert result["status"] == "blocked"

    def test_logs_block(self, db):
        task = _make_task(db)
        block_task(db, task["id"])
        entries = get_log(db, task["id"], type="transition")
        assert any("blocked" in e["message"] for e in entries)


class TestGetUnresolvedDeps:
    def test_no_deps(self, db):
        task = _make_task(db)
        assert get_unresolved_deps(db, task["id"]) == []

    def test_unresolved(self, db):
        t1 = _make_task(db, "Dep")
        t2 = _make_task(db, "Main", deps=[t1["id"]])
        unresolved = get_unresolved_deps(db, t2["id"])
        assert unresolved == [t1["id"]]

    def test_resolved(self, db):
        t1 = _make_task(db, "Dep")
        t2 = _make_task(db, "Main", deps=[t1["id"]])
        update_task(db, t1["id"], stage="done")
        assert get_unresolved_deps(db, t2["id"]) == []

    def test_mixed(self, db):
        t1 = _make_task(db, "Done dep")
        t2 = _make_task(db, "Not done dep")
        t3 = _make_task(db, "Main", deps=[t1["id"], t2["id"]])
        update_task(db, t1["id"], stage="done")
        unresolved = get_unresolved_deps(db, t3["id"])
        assert unresolved == [t2["id"]]
