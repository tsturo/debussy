"""Task CRUD and query functions for takt."""

from __future__ import annotations

import json
import os
import sqlite3


def generate_id() -> str:
    """Generate a task ID like 'takt-a3f2dd'."""
    return "takt-" + os.urandom(3).hex()


def _task_row_to_dict(row: sqlite3.Row, deps: list[str] | None = None) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d["dependencies"] = deps if deps is not None else []
    return d


def _get_deps(db: sqlite3.Connection, task_id: str) -> list[str]:
    rows = db.execute(
        "SELECT depends_on_id FROM dependencies WHERE task_id = ?", (task_id,)
    ).fetchall()
    return [r["depends_on_id"] for r in rows]


def create_task(
    db: sqlite3.Connection,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    deps: list[str] | None = None,
) -> dict:
    """Create a new task and return its dict representation."""
    task_id = generate_id()
    tags_json = json.dumps(tags or [])
    db.execute(
        "INSERT INTO tasks (id, title, description, tags) VALUES (?, ?, ?, ?)",
        (task_id, title, description, tags_json),
    )
    for dep_id in (deps or []):
        db.execute(
            "INSERT INTO dependencies (task_id, depends_on_id) VALUES (?, ?)",
            (task_id, dep_id),
        )
    return get_task(db, task_id)  # type: ignore[return-value]


def get_task(db: sqlite3.Connection, task_id: str) -> dict | None:
    """Return a task dict with dependencies, or None if not found."""
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    deps = _get_deps(db, task_id)
    return _task_row_to_dict(row, deps)


def list_tasks(
    db: sqlite3.Connection,
    stage: str | None = None,
    status: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    """List tasks with optional filters."""
    conditions = []
    params: list[str] = []

    if stage is not None:
        conditions.append("stage = ?")
        params.append(stage)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if tag is not None:
        conditions.append("EXISTS (SELECT 1 FROM json_each(tags) WHERE value = ?)")
        params.append(tag)

    query = "SELECT * FROM tasks"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at"

    rows = db.execute(query, params).fetchall()
    results = []
    for row in rows:
        deps = _get_deps(db, row["id"])
        results.append(_task_row_to_dict(row, deps))
    return results


def update_task(db: sqlite3.Connection, task_id: str, **fields) -> dict:
    """Update mutable fields on a task. Returns updated task dict."""
    allowed = {"title", "description", "stage", "status", "tags", "rejection_count"}
    to_set = {}
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Cannot update field: {k}")
        if k == "tags" and isinstance(v, list):
            v = json.dumps(v)
        to_set[k] = v

    if not to_set:
        return get_task(db, task_id)  # type: ignore[return-value]

    to_set["updated_at"] = "datetime('now')"
    set_parts = []
    params: list = []
    for k, v in to_set.items():
        if k == "updated_at":
            set_parts.append("updated_at = datetime('now')")
        else:
            set_parts.append(f"{k} = ?")
            params.append(v)
    params.append(task_id)

    db.execute(
        f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?",
        params,
    )
    return get_task(db, task_id)  # type: ignore[return-value]
