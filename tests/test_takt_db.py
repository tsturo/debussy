"""Tests for takt database layer."""

import sqlite3
import threading

import pytest

from debussy.takt.db import get_db, init_db, SCHEMA_VERSION


@pytest.fixture
def db_dir(tmp_path):
    """Provide a temporary directory for takt database."""
    return tmp_path


class TestGetDb:
    def test_returns_connection(self, db_dir):
        with get_db(db_dir) as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_wal_mode(self, db_dir):
        with get_db(db_dir) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal"

    def test_foreign_keys_enabled(self, db_dir):
        with get_db(db_dir) as conn:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1

    def test_busy_timeout(self, db_dir):
        with get_db(db_dir) as conn:
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            assert timeout == 5000

    def test_creates_takt_directory(self, db_dir):
        takt_dir = db_dir / ".takt"
        assert not takt_dir.exists()
        with get_db(db_dir):
            pass
        assert takt_dir.is_dir()

    def test_creates_db_file(self, db_dir):
        db_file = db_dir / ".takt" / "takt.db"
        assert not db_file.exists()
        with get_db(db_dir):
            pass
        assert db_file.is_file()

    def test_schema_version(self, db_dir):
        with get_db(db_dir) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert version == SCHEMA_VERSION


class TestSchema:
    def test_tasks_table_exists(self, db_dir):
        with get_db(db_dir) as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "tasks" in tables

    def test_dependencies_table_exists(self, db_dir):
        with get_db(db_dir) as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "dependencies" in tables

    def test_log_table_exists(self, db_dir):
        with get_db(db_dir) as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "log" in tables

    def test_indexes_created(self, db_dir):
        expected = {
            "idx_tasks_stage_status",
            "idx_log_task_id",
            "idx_deps_task",
            "idx_deps_dep",
        }
        with get_db(db_dir) as conn:
            indexes = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
            assert expected.issubset(indexes)

    def test_tasks_stage_constraint(self, db_dir):
        with get_db(db_dir) as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO tasks (id, title, stage) VALUES ('t1', 'test', 'invalid')"
                )

    def test_tasks_status_constraint(self, db_dir):
        with get_db(db_dir) as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO tasks (id, title, status) VALUES ('t1', 'test', 'invalid')"
                )

    def test_tasks_defaults(self, db_dir):
        with get_db(db_dir) as conn:
            conn.execute("INSERT INTO tasks (id, title) VALUES ('t1', 'test')")
            row = conn.execute("SELECT * FROM tasks WHERE id='t1'").fetchone()
            assert row["stage"] == "backlog"
            assert row["status"] == "pending"
            assert row["tags"] == "[]"
            assert row["rejection_count"] == 0
            assert row["description"] == ""

    def test_log_type_constraint(self, db_dir):
        with get_db(db_dir) as conn:
            conn.execute("INSERT INTO tasks (id, title) VALUES ('t1', 'test')")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO log (task_id, type, message) VALUES ('t1', 'bad', 'msg')"
                )


class TestConcurrency:
    def test_multiple_connections(self, db_dir):
        """Opening get_db twice sequentially works without locking."""
        with get_db(db_dir) as conn1:
            conn1.execute("INSERT INTO tasks (id, title) VALUES ('t1', 'first')")
        with get_db(db_dir) as conn2:
            row = conn2.execute("SELECT title FROM tasks WHERE id='t1'").fetchone()
            assert row["title"] == "first"

    def test_concurrent_readers(self, db_dir):
        """Multiple threads can read concurrently."""
        with get_db(db_dir) as conn:
            conn.execute("INSERT INTO tasks (id, title) VALUES ('t1', 'test')")

        results = []
        errors = []

        def reader():
            try:
                with get_db(db_dir) as conn:
                    row = conn.execute("SELECT title FROM tasks WHERE id='t1'").fetchone()
                    results.append(row["title"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert len(results) == 8
        assert all(r == "test" for r in results)


class TestInitDb:
    def test_init_creates_db(self, db_dir):
        init_db(db_dir)
        assert (db_dir / ".takt" / "takt.db").is_file()

    def test_init_idempotent(self, db_dir):
        init_db(db_dir)
        init_db(db_dir)
        assert (db_dir / ".takt" / "takt.db").is_file()
