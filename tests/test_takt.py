"""End-to-end tests for the takt module."""

import threading

import pytest

from debussy.takt import (
    get_db,
    init_db,
    create_task,
    get_task,
    list_tasks,
    update_task,
    add_comment,
    advance_task,
    block_task,
    claim_task,
    get_log,
    get_unresolved_deps,
    reject_task,
    release_task,
)


@pytest.fixture
def db(tmp_path):
    init_db(tmp_path)
    with get_db(tmp_path) as conn:
        yield conn


@pytest.fixture
def db_dir(tmp_path):
    init_db(tmp_path)
    return tmp_path


class TestFullLifecycle:
    def test_task_through_full_pipeline(self, db):
        """Create a task and advance it through backlog → development → reviewing → merging → done."""
        task = create_task(db, "Implement feature", description="Build the thing")
        assert task["stage"] == "backlog"
        assert task["status"] == "pending"

        # Advance backlog → development
        task = advance_task(db, task["id"])
        assert task["stage"] == "development"

        # Developer claims
        task = claim_task(db, task["id"], "developer-1")
        assert task["status"] == "active"

        # Developer finishes, releases
        task = release_task(db, task["id"])
        assert task["status"] == "pending"

        # Advance development → reviewing
        task = advance_task(db, task["id"])
        assert task["stage"] == "reviewing"

        # Advance reviewing → merging
        task = advance_task(db, task["id"])
        assert task["stage"] == "merging"

        # Advance merging → done
        task = advance_task(db, task["id"])
        assert task["stage"] == "done"

        # Verify log has all transitions
        entries = get_log(db, task["id"], type="transition")
        messages = [e["message"] for e in entries]
        assert any("backlog -> development" in m for m in messages)
        assert any("development -> reviewing" in m for m in messages)
        assert any("reviewing -> merging" in m for m in messages)
        assert any("merging -> done" in m for m in messages)

    def test_security_pipeline(self, db):
        """Security-tagged task routes through security_review."""
        task = create_task(db, "Auth module", tags=["security"])
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing
        task = advance_task(db, task["id"])  # → security_review (not merging)
        assert task["stage"] == "security_review"
        task = advance_task(db, task["id"])  # → merging
        assert task["stage"] == "merging"
        task = advance_task(db, task["id"])  # → done
        assert task["stage"] == "done"

    def test_rejection_cycle(self, db):
        """Task gets rejected, returns to development, counter increments."""
        task = create_task(db, "Buggy feature")
        advance_task(db, task["id"])  # → development
        advance_task(db, task["id"])  # → reviewing

        task = reject_task(db, task["id"], author="reviewer-1")
        assert task["stage"] == "development"
        assert task["rejection_count"] == 1

        # Advance again to reviewing, reject again
        advance_task(db, task["id"])  # → reviewing
        task = reject_task(db, task["id"])
        assert task["rejection_count"] == 2

        # Third rejection auto-blocks
        advance_task(db, task["id"])  # → reviewing
        task = reject_task(db, task["id"])
        assert task["rejection_count"] == 3
        assert task["status"] == "blocked"

    def test_dependencies(self, db):
        """Create tasks with deps, verify resolution."""
        t1 = create_task(db, "Foundation")
        t2 = create_task(db, "Building", deps=[t1["id"]])

        assert get_unresolved_deps(db, t2["id"]) == [t1["id"]]

        # Complete t1
        advance_task(db, t1["id"])  # → development
        advance_task(db, t1["id"])  # → reviewing
        advance_task(db, t1["id"])  # → merging
        advance_task(db, t1["id"])  # → done

        assert get_unresolved_deps(db, t2["id"]) == []

    def test_comments_and_log(self, db):
        """Add comments, read log entries."""
        task = create_task(db, "Task")
        add_comment(db, task["id"], "dev", "Starting work")
        add_comment(db, task["id"], "dev", "Making progress")
        advance_task(db, task["id"])

        all_entries = get_log(db, task["id"])
        assert len(all_entries) == 3  # 2 comments + 1 transition

        comments = get_log(db, task["id"], type="comment")
        assert len(comments) == 2
        assert comments[0]["message"] == "Starting work"

    def test_list_and_filter(self, db):
        """Create multiple tasks, filter by various criteria."""
        t1 = create_task(db, "Normal task")
        t2 = create_task(db, "Security task", tags=["security"])
        t3 = create_task(db, "Frontend task", tags=["frontend"])

        # All in backlog
        assert len(list_tasks(db)) == 3
        assert len(list_tasks(db, stage="backlog")) == 3

        # Advance one to development
        advance_task(db, t1["id"])
        assert len(list_tasks(db, stage="backlog")) == 2
        assert len(list_tasks(db, stage="development")) == 1

        # Filter by tag
        assert len(list_tasks(db, tag="security")) == 1
        assert list_tasks(db, tag="security")[0]["id"] == t2["id"]

        # Filter by status
        claim_task(db, t1["id"], "dev")
        assert len(list_tasks(db, status="active")) == 1

    def test_block_task(self, db):
        """Block a task, verify status."""
        task = create_task(db, "Stuck task")
        advance_task(db, task["id"])
        task = block_task(db, task["id"])
        assert task["status"] == "blocked"
        entries = get_log(db, task["id"], type="transition")
        assert any("blocked" in e["message"] for e in entries)


class TestConcurrentAccess:
    def test_readers_and_writer(self, db_dir):
        """8 reader threads + 1 writer thread, no errors."""
        # Set up initial data
        with get_db(db_dir) as db:
            for i in range(10):
                create_task(db, f"Task {i}")

        errors = []
        results = []

        def reader():
            try:
                with get_db(db_dir) as db:
                    tasks = list_tasks(db)
                    results.append(len(tasks))
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                with get_db(db_dir) as db:
                    for i in range(10, 20):
                        create_task(db, f"Task {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Errors during concurrent access: {errors}"
        assert len(results) == 8
        # Each reader should see at least the initial 10 tasks
        assert all(r >= 10 for r in results)


class TestPublicAPIImports:
    def test_all_exports_available(self):
        """Verify all public API functions are importable from debussy.takt."""
        from debussy.takt import (
            get_db, init_db,
            create_task, get_task, list_tasks, update_task,
            add_comment, advance_task, block_task, claim_task,
            get_log, get_unresolved_deps, reject_task, release_task,
        )
        # Just verify they're callable
        for fn in [get_db, init_db, create_task, get_task, list_tasks,
                   update_task, add_comment, advance_task, block_task,
                   claim_task, get_log, get_unresolved_deps, reject_task,
                   release_task]:
            assert callable(fn)
