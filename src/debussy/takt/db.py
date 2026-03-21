"""SQLite connection management for takt."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 4

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    seq             INTEGER NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    stage           TEXT DEFAULT 'backlog'
                    CHECK(stage IN ('backlog','development','reviewing',
                                    'security_review','merging','acceptance',
                                    'ux_review','perf_review','done')),
    status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','active','blocked')),
    tags            TEXT DEFAULT '[]',
    rejection_count INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dependencies (
    task_id       TEXT REFERENCES tasks(id),
    depends_on_id TEXT REFERENCES tasks(id),
    PRIMARY KEY (task_id, depends_on_id)
);

CREATE TABLE IF NOT EXISTS log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT REFERENCES tasks(id),
    timestamp TEXT DEFAULT (datetime('now')),
    type      TEXT CHECK(type IN ('comment','transition','assignment')),
    author    TEXT,
    message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_stage_status ON tasks(stage, status);
CREATE INDEX IF NOT EXISTS idx_log_task_id ON log(task_id);
CREATE INDEX IF NOT EXISTS idx_deps_task ON dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_deps_dep ON dependencies(depends_on_id);

CREATE TABLE IF NOT EXISTS projects (
    prefix     TEXT PRIMARY KEY CHECK(length(prefix) BETWEEN 2 AND 5),
    name       TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    next_seq   INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_default ON projects(is_default) WHERE is_default = 1;
"""


def _find_project_root(start: Path | None = None) -> Path:
    """Walk up from start to find a directory containing .takt/ or .git/."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".takt").is_dir() or (parent / ".git").is_dir():
            return parent
    return current


def _derive_prefix(project_dir: Path) -> str:
    name = project_dir.name.lower().replace("-", "").replace("_", "").replace(" ", "")
    consonants = [c for c in name if c.isalpha() and c not in "aeiou"]
    if len(consonants) >= 3:
        return "".join(consonants[:3]).upper()
    chars = [c for c in name if c.isalpha()]
    return "".join(chars[:3]).upper() or "TSK"


def get_prefix(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT prefix FROM projects WHERE is_default = 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("No default project. Run: takt project add <PREFIX> <NAME> --default")
    return row["prefix"]


def _ensure_default_project(conn: sqlite3.Connection, project_dir: Path) -> None:
    row = conn.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
    if row is None:
        prefix = _derive_prefix(project_dir)
        conn.execute(
            "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES (?, ?, 1, 1)",
            (prefix, prefix),
        )


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "tasks" not in tables:
            return
        if "metadata" not in tables:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metadata "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "seq" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN seq INTEGER")
            rows = conn.execute(
                "SELECT id FROM tasks ORDER BY created_at"
            ).fetchall()
            for i, row in enumerate(rows, 1):
                conn.execute("UPDATE tasks SET seq = ? WHERE id = ?", (i, row["id"]))
            if rows:
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('next_seq', ?)",
                    (str(len(rows) + 1),),
                )
    if version < 3:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS projects ("
            "prefix TEXT PRIMARY KEY CHECK(length(prefix) BETWEEN 2 AND 5), "
            "name TEXT NOT NULL, "
            "is_default INTEGER NOT NULL DEFAULT 0, "
            "next_seq INTEGER NOT NULL DEFAULT 1)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_default "
            "ON projects(is_default) WHERE is_default = 1"
        )
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "metadata" in tables:
            prefix_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'prefix'"
            ).fetchone()
            seq_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'next_seq'"
            ).fetchone()
            if prefix_row:
                prefix = prefix_row[0] if isinstance(prefix_row, tuple) else prefix_row["value"]
                next_seq = int(seq_row[0] if isinstance(seq_row, tuple) else seq_row["value"]) if seq_row else 1
                conn.execute(
                    "INSERT OR IGNORE INTO projects (prefix, name, is_default, next_seq) "
                    "VALUES (?, ?, 1, ?)",
                    (prefix, prefix, next_seq),
                )
                conn.execute("DELETE FROM metadata WHERE key = 'prefix'")
                conn.execute("DELETE FROM metadata WHERE key = 'next_seq'")
    if version < 4:
        has_unique = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if has_unique and "UNIQUE" in (has_unique[0] or ""):
            conn.execute("ALTER TABLE tasks RENAME TO tasks_old")
            conn.execute(
                "CREATE TABLE tasks ("
                "id TEXT PRIMARY KEY, seq INTEGER NOT NULL, "
                "title TEXT NOT NULL, description TEXT DEFAULT '', "
                "stage TEXT DEFAULT 'backlog' "
                "CHECK(stage IN ('backlog','development','reviewing',"
                "'security_review','merging','acceptance',"
                "'ux_review','perf_review','done')), "
                "status TEXT DEFAULT 'pending' "
                "CHECK(status IN ('pending','active','blocked')), "
                "tags TEXT DEFAULT '[]', "
                "rejection_count INTEGER DEFAULT 0, "
                "created_at TEXT DEFAULT (datetime('now')), "
                "updated_at TEXT DEFAULT (datetime('now')))"
            )
            conn.execute("INSERT INTO tasks SELECT * FROM tasks_old")
            conn.execute("DROP TABLE tasks_old")
    conn.commit()
    conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)


_SCHEMA_STATEMENTS = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]


def _apply_schema(conn: sqlite3.Connection) -> None:
    _migrate(conn)
    for stmt in _SCHEMA_STATEMENTS:
        conn.execute(stmt)
    conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)


def _configure(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if row and row[0] != "wal":
        import logging
        logging.warning("takt: WAL mode not available (mode=%s), concurrent access may be unreliable", row[0])
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")


@contextmanager
def get_db(project_dir: Path | str | None = None):
    """Context manager that yields a configured SQLite connection.

    Auto-creates .takt/ directory and schema if missing.
    """
    root = Path(project_dir) if project_dir else _find_project_root()
    takt_dir = root / ".takt"
    if takt_dir.is_symlink():
        raise RuntimeError(
            f"{takt_dir} is a symlink (-> {takt_dir.resolve()}). "
            "Remove it and recreate as a real directory."
        )
    takt_dir.mkdir(parents=True, exist_ok=True)
    db_path = takt_dir / "takt.db"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        _configure(conn)
        _apply_schema(conn)
        _ensure_default_project(conn, root)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(project_dir: Path | str | None = None) -> None:
    """Create or verify the takt database."""
    with get_db(project_dir):
        pass
