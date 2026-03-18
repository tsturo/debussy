"""Unified log and workflow operations for takt."""

from __future__ import annotations

import json
import sqlite3

from .models import get_task, update_task

MAX_REJECTIONS = 3

NEXT_STAGE = {
    "backlog": "development",
    "development": "reviewing",
    "reviewing": "merging",
    "security_review": "merging",
    "merging": "done",
    "acceptance": "done",
}

SECURITY_NEXT_STAGE = {
    "reviewing": "security_review",
}


# --- Log operations ---

def add_log(db: sqlite3.Connection, task_id: str, type: str, author: str, message: str) -> None:
    """Insert a log entry."""
    db.execute(
        "INSERT INTO log (task_id, type, author, message) VALUES (?, ?, ?, ?)",
        (task_id, type, author, message),
    )


def add_comment(db: sqlite3.Connection, task_id: str, author: str, message: str) -> None:
    """Add a comment log entry."""
    add_log(db, task_id, "comment", author, message)


def get_log(db: sqlite3.Connection, task_id: str, type: str | None = None) -> list[dict]:
    """Return log entries for a task, optionally filtered by type."""
    if type is not None:
        rows = db.execute(
            "SELECT * FROM log WHERE task_id = ? AND type = ? ORDER BY id",
            (task_id, type),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM log WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Workflow operations ---

def advance_task(db: sqlite3.Connection, task_id: str, to_stage: str | None = None) -> dict:
    """Move a task to the next stage (or a specific stage). Logs the transition."""
    task = get_task(db, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    current = task["stage"]
    if to_stage is not None:
        next_stage = to_stage
    else:
        # Check security routing
        has_security = "security" in task["tags"]
        if has_security and current in SECURITY_NEXT_STAGE:
            next_stage = SECURITY_NEXT_STAGE[current]
        elif current in NEXT_STAGE:
            next_stage = NEXT_STAGE[current]
        else:
            raise ValueError(f"No next stage from: {current}")

    updated = update_task(db, task_id, stage=next_stage, status="pending")
    add_log(db, task_id, "transition", "system", f"{current} -> {next_stage}")
    return updated


def reject_task(db: sqlite3.Connection, task_id: str, author: str | None = None) -> dict:
    """Reject a task: increment counter, return to development or block after 3."""
    task = get_task(db, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    new_count = task["rejection_count"] + 1
    who = author or "system"

    if new_count >= MAX_REJECTIONS:
        updated = update_task(db, task_id, rejection_count=new_count,
                              stage="development", status="blocked")
        add_log(db, task_id, "transition", who,
                f"rejected (count={new_count}), auto-blocked")
    else:
        updated = update_task(db, task_id, rejection_count=new_count,
                              stage="development", status="pending")
        add_log(db, task_id, "transition", who,
                f"rejected (count={new_count}), back to development")
    return updated


def claim_task(db: sqlite3.Connection, task_id: str, agent: str) -> dict:
    """Claim a task: set status=active, log assignment."""
    updated = update_task(db, task_id, status="active")
    add_log(db, task_id, "assignment", agent, f"claimed by {agent}")
    return updated


def release_task(db: sqlite3.Connection, task_id: str) -> dict:
    """Release a task: set status=pending, log transition."""
    updated = update_task(db, task_id, status="pending")
    add_log(db, task_id, "transition", "system", "released")
    return updated


def block_task(db: sqlite3.Connection, task_id: str) -> dict:
    """Block a task: set status=blocked, log transition."""
    updated = update_task(db, task_id, status="blocked")
    add_log(db, task_id, "transition", "system", "blocked")
    return updated


def get_unresolved_deps(db: sqlite3.Connection, task_id: str) -> list[str]:
    """Return dependency IDs where the dependency's stage is not 'done'."""
    rows = db.execute(
        """SELECT d.depends_on_id FROM dependencies d
           JOIN tasks t ON t.id = d.depends_on_id
           WHERE d.task_id = ? AND t.stage != 'done'""",
        (task_id,),
    ).fetchall()
    return [r["depends_on_id"] for r in rows]
