"""Tests for takt task model."""

import pytest

from debussy.takt.db import get_db
from debussy.takt.models import create_task, get_task, list_tasks, update_task, generate_id


@pytest.fixture
def db(tmp_path):
    with get_db(tmp_path) as conn:
        yield conn


class TestGenerateId:
    def test_format(self):
        tid = generate_id()
        assert tid.startswith("takt-")
        assert len(tid) == 11  # "takt-" + 6 hex chars

    def test_unique(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


class TestCreateTask:
    def test_basic(self, db):
        task = create_task(db, "Build thing")
        assert task["id"].startswith("takt-")
        assert task["title"] == "Build thing"
        assert task["stage"] == "backlog"
        assert task["status"] == "pending"
        assert task["tags"] == []
        assert task["rejection_count"] == 0
        assert task["dependencies"] == []

    def test_with_description(self, db):
        task = create_task(db, "Build thing", description="Details here")
        assert task["description"] == "Details here"

    def test_with_tags(self, db):
        task = create_task(db, "Secure thing", tags=["security", "frontend"])
        assert task["tags"] == ["security", "frontend"]

    def test_with_deps(self, db):
        t1 = create_task(db, "First")
        t2 = create_task(db, "Second", deps=[t1["id"]])
        assert t2["dependencies"] == [t1["id"]]

    def test_with_multiple_deps(self, db):
        t1 = create_task(db, "First")
        t2 = create_task(db, "Second")
        t3 = create_task(db, "Third", deps=[t1["id"], t2["id"]])
        assert set(t3["dependencies"]) == {t1["id"], t2["id"]}


class TestGetTask:
    def test_found(self, db):
        created = create_task(db, "Test")
        fetched = get_task(db, created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["title"] == "Test"

    def test_not_found(self, db):
        assert get_task(db, "takt-nonexistent") is None

    def test_includes_deps(self, db):
        t1 = create_task(db, "Dep")
        t2 = create_task(db, "Main", deps=[t1["id"]])
        fetched = get_task(db, t2["id"])
        assert fetched["dependencies"] == [t1["id"]]


class TestListTasks:
    def test_all(self, db):
        create_task(db, "A")
        create_task(db, "B")
        tasks = list_tasks(db)
        assert len(tasks) == 2

    def test_filter_stage(self, db):
        create_task(db, "A")
        t2 = create_task(db, "B")
        update_task(db, t2["id"], stage="development")
        assert len(list_tasks(db, stage="backlog")) == 1
        assert len(list_tasks(db, stage="development")) == 1

    def test_filter_status(self, db):
        create_task(db, "A")
        t2 = create_task(db, "B")
        update_task(db, t2["id"], status="active")
        assert len(list_tasks(db, status="pending")) == 1
        assert len(list_tasks(db, status="active")) == 1

    def test_filter_tag(self, db):
        create_task(db, "Normal")
        create_task(db, "Secure", tags=["security"])
        create_task(db, "Frontend", tags=["frontend"])
        assert len(list_tasks(db, tag="security")) == 1
        assert len(list_tasks(db, tag="frontend")) == 1
        assert len(list_tasks(db)) == 3

    def test_combined_filters(self, db):
        create_task(db, "A", tags=["security"])
        t2 = create_task(db, "B", tags=["security"])
        update_task(db, t2["id"], stage="development")
        results = list_tasks(db, stage="development", tag="security")
        assert len(results) == 1
        assert results[0]["title"] == "B"

    def test_empty(self, db):
        assert list_tasks(db) == []


class TestUpdateTask:
    def test_update_title(self, db):
        task = create_task(db, "Old")
        updated = update_task(db, task["id"], title="New")
        assert updated["title"] == "New"

    def test_update_stage(self, db):
        task = create_task(db, "Test")
        updated = update_task(db, task["id"], stage="development")
        assert updated["stage"] == "development"

    def test_update_status(self, db):
        task = create_task(db, "Test")
        updated = update_task(db, task["id"], status="active")
        assert updated["status"] == "active"

    def test_update_tags(self, db):
        task = create_task(db, "Test")
        updated = update_task(db, task["id"], tags=["security"])
        assert updated["tags"] == ["security"]

    def test_update_bumps_updated_at(self, db):
        task = create_task(db, "Test")
        original_updated = task["updated_at"]
        # Force a different timestamp by inserting a small delay via SQL
        db.execute("UPDATE tasks SET updated_at = '2020-01-01 00:00:00' WHERE id = ?",
                   (task["id"],))
        updated = update_task(db, task["id"], title="Changed")
        assert updated["updated_at"] != "2020-01-01 00:00:00"

    def test_invalid_field_raises(self, db):
        task = create_task(db, "Test")
        with pytest.raises(ValueError, match="Cannot update field"):
            update_task(db, task["id"], id="new-id")

    def test_no_fields_returns_unchanged(self, db):
        task = create_task(db, "Test")
        result = update_task(db, task["id"])
        assert result["title"] == "Test"

    def test_update_rejection_count(self, db):
        task = create_task(db, "Test")
        updated = update_task(db, task["id"], rejection_count=2)
        assert updated["rejection_count"] == 2
