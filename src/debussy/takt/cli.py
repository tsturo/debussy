"""Thin CLI for takt task management."""

from __future__ import annotations

import argparse
import json
import sys

from .db import get_db, get_prefix, init_db, _find_project_root
from .models import create_task, get_task, list_tasks, update_task
from .log import (
    add_comment,
    advance_task,
    block_task,
    claim_task,
    get_log,
    reject_task,
    release_task,
)


def _print_task(task: dict) -> None:
    print(f"id:          {task['id']}")
    print(f"title:       {task['title']}")
    if task["description"]:
        print(f"description: {task['description']}")
    print(f"stage:       {task['stage']}")
    print(f"status:      {task['status']}")
    if task["tags"]:
        print(f"tags:        {', '.join(task['tags'])}")
    if task["dependencies"]:
        print(f"deps:        {', '.join(task['dependencies'])}")
    if task["rejection_count"]:
        print(f"rejections:  {task['rejection_count']}")
    print(f"created:     {task['created_at']}")
    print(f"updated:     {task['updated_at']}")


def _print_task_list(tasks: list[dict]) -> None:
    if not tasks:
        print("No tasks found.")
        return
    # Column widths
    id_w = max(len(t["id"]) for t in tasks)
    title_w = max(len(t["title"]) for t in tasks)
    stage_w = max(len(t["stage"]) for t in tasks)
    status_w = max(len(t["status"]) for t in tasks)

    header = f"{'ID':<{id_w}}  {'TITLE':<{title_w}}  {'STAGE':<{stage_w}}  {'STATUS':<{status_w}}  TAGS"
    print(header)
    print("-" * len(header))
    for t in tasks:
        tags = ",".join(t["tags"]) if t["tags"] else ""
        print(f"{t['id']:<{id_w}}  {t['title']:<{title_w}}  {t['stage']:<{stage_w}}  {t['status']:<{status_w}}  {tags}")


def _print_log(entries: list[dict]) -> None:
    if not entries:
        print("No log entries.")
        return
    for e in entries:
        print(f"[{e['timestamp']}] ({e['type']}) {e['author']}: {e['message']}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="takt", description="Task management for debussy")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize takt database")

    p_prefix = sub.add_parser("prefix", help="Show or set the project prefix")
    p_prefix.add_argument("value", nargs="?", help="New prefix (2-5 uppercase letters)")

    p_create = sub.add_parser("create", help="Create a task")
    p_create.add_argument("title")
    p_create.add_argument("-d", "--description", default="")
    p_create.add_argument("--deps", help="Comma-separated dependency IDs")
    p_create.add_argument("--tags", help="Comma-separated tags")

    p_show = sub.add_parser("show", help="Show a task")
    p_show.add_argument("id")
    p_show.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--stage")
    p_list.add_argument("--status")
    p_list.add_argument("--tag")
    p_list.add_argument("--json", action="store_true")

    p_advance = sub.add_parser("advance", help="Advance task to next stage")
    p_advance.add_argument("id")
    p_advance.add_argument("--to", dest="to_stage")

    p_reject = sub.add_parser("reject", help="Reject a task")
    p_reject.add_argument("id")

    p_claim = sub.add_parser("claim", help="Claim a task")
    p_claim.add_argument("id")
    p_claim.add_argument("--agent", required=True)

    p_release = sub.add_parser("release", help="Release a task")
    p_release.add_argument("id")

    p_block = sub.add_parser("block", help="Block a task")
    p_block.add_argument("id")

    p_comment = sub.add_parser("comment", help="Add a comment")
    p_comment.add_argument("id")
    p_comment.add_argument("message")
    p_comment.add_argument("--author", default="user")

    p_log = sub.add_parser("log", help="Show task log")
    p_log.add_argument("id")
    p_log.add_argument("--type", choices=["transition", "comment", "assignment"])

    p_project = sub.add_parser("project", help="Manage projects")
    project_sub = p_project.add_subparsers(dest="project_command")

    p_proj_add = project_sub.add_parser("add", help="Add a project")
    p_proj_add.add_argument("prefix", help="2-5 uppercase letters")
    p_proj_add.add_argument("name", help="Human-readable name")
    p_proj_add.add_argument("--default", action="store_true")

    project_sub.add_parser("list", help="List projects")

    p_proj_default = project_sub.add_parser("default", help="Show or switch default project")
    p_proj_default.add_argument("prefix", nargs="?", help="Switch default to this prefix")

    p_proj_rm = project_sub.add_parser("rm", help="Remove a project")
    p_proj_rm.add_argument("prefix")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "init":
        root = _find_project_root()
        init_db(root)
        with get_db(root) as db:
            prefix = get_prefix(db)
        print(f"Initialized takt database at {root / '.takt' / 'takt.db'} (prefix: {prefix})")
        return 0

    root = _find_project_root()
    try:
        with get_db(root) as db:
            return _dispatch(args, db)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, db) -> int:
    cmd = args.command

    if cmd == "prefix":
        if args.value:
            val = args.value.upper()
            if not val.isalpha() or not (2 <= len(val) <= 5):
                print("Prefix must be 2-5 letters", file=sys.stderr)
                return 1
            db.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('prefix', ?)",
                (val,),
            )
            print(f"Prefix set to: {val}")
        else:
            print(get_prefix(db))
        return 0

    if cmd == "create":
        deps = [d.strip() for d in args.deps.split(",")] if args.deps else None
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        task = create_task(db, args.title, description=args.description,
                           tags=tags, deps=deps)
        print(task["id"])
        return 0

    if cmd == "show":
        task = get_task(db, args.id)
        if task is None:
            print(f"Task not found: {args.id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(task, indent=2))
        else:
            _print_task(task)
        return 0

    if cmd == "list":
        tasks = list_tasks(db, stage=args.stage, status=args.status, tag=args.tag)
        if args.json:
            print(json.dumps(tasks, indent=2))
        else:
            _print_task_list(tasks)
        return 0

    if cmd == "advance":
        task = advance_task(db, args.id, to_stage=args.to_stage)
        print(f"{task['id']}: {task['stage']}")
        return 0

    if cmd == "reject":
        task = reject_task(db, args.id)
        print(f"{task['id']}: rejected (count={task['rejection_count']})")
        return 0

    if cmd == "claim":
        task = claim_task(db, args.id, args.agent)
        print(f"{task['id']}: claimed by {args.agent}")
        return 0

    if cmd == "release":
        task = release_task(db, args.id)
        print(f"{task['id']}: released")
        return 0

    if cmd == "block":
        task = block_task(db, args.id)
        print(f"{task['id']}: blocked")
        return 0

    if cmd == "comment":
        add_comment(db, args.id, args.author, args.message)
        print("Comment added.")
        return 0

    if cmd == "log":
        entries = get_log(db, args.id, type=args.type)
        _print_log(entries)
        return 0

    if cmd == "project":
        return _handle_project(args, db)

    return 1


def _handle_project(args: argparse.Namespace, db) -> int:
    sub = args.project_command

    if sub == "add":
        return _project_add(args, db)
    if sub == "list":
        return _project_list(db)
    if sub == "default":
        return _project_default(args, db)
    if sub == "rm":
        return _project_rm(args, db)

    print("Usage: takt project {add,list,default,rm}", file=sys.stderr)
    return 1


def _project_add(args: argparse.Namespace, db) -> int:
    prefix = args.prefix.upper()
    if not prefix.isalpha() or not (2 <= len(prefix) <= 5):
        print("Prefix must be 2-5 letters", file=sys.stderr)
        return 1
    existing = db.execute("SELECT 1 FROM projects WHERE prefix = ?", (prefix,)).fetchone()
    if existing:
        print(f"Project {prefix} already exists", file=sys.stderr)
        return 1
    next_seq = 1
    max_row = db.execute(
        "SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM tasks WHERE id LIKE ?",
        (len(prefix) + 2, f"{prefix}-%"),
    ).fetchone()
    if max_row and max_row[0] is not None:
        next_seq = max_row[0] + 1
    if args.default:
        db.execute("UPDATE projects SET is_default = 0 WHERE is_default = 1")
    has_any = db.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
    is_default = 1 if (args.default or not has_any) else 0
    db.execute(
        "INSERT INTO projects (prefix, name, is_default, next_seq) VALUES (?, ?, ?, ?)",
        (prefix, args.name, is_default, next_seq),
    )
    marker = " (default)" if is_default else ""
    print(f"Added project: {prefix} — {args.name}{marker}")
    return 0


def _project_list(db) -> int:
    rows = db.execute(
        "SELECT p.prefix, p.name, p.is_default, p.next_seq, "
        "(SELECT COUNT(*) FROM tasks WHERE id LIKE p.prefix || '-%') AS task_count "
        "FROM projects p ORDER BY p.is_default DESC, p.prefix"
    ).fetchall()
    if not rows:
        print("No projects.")
        return 0
    for r in rows:
        default = " *" if r["is_default"] else ""
        print(f"{r['prefix']}{default}  {r['name']}  ({r['task_count']} tasks)")
    return 0


def _project_default(args: argparse.Namespace, db) -> int:
    if args.prefix:
        prefix = args.prefix.upper()
        row = db.execute("SELECT 1 FROM projects WHERE prefix = ?", (prefix,)).fetchone()
        if not row:
            print(f"Project not found: {prefix}", file=sys.stderr)
            return 1
        db.execute("UPDATE projects SET is_default = 0 WHERE is_default = 1")
        db.execute("UPDATE projects SET is_default = 1 WHERE prefix = ?", (prefix,))
        print(f"Default project: {prefix}")
    else:
        print(get_prefix(db))
    return 0


def _project_rm(args: argparse.Namespace, db) -> int:
    prefix = args.prefix.upper()
    is_default = db.execute(
        "SELECT is_default FROM projects WHERE prefix = ?", (prefix,)
    ).fetchone()
    if not is_default:
        print(f"Project not found: {prefix}", file=sys.stderr)
        return 1
    if is_default["is_default"]:
        print("Cannot remove default project. Switch default first.", file=sys.stderr)
        return 1
    has_tasks = db.execute(
        "SELECT 1 FROM tasks WHERE id LIKE ?", (f"{prefix}-%",)
    ).fetchone()
    if has_tasks:
        print(f"Cannot remove {prefix}: tasks still reference it", file=sys.stderr)
        return 1
    db.execute("DELETE FROM projects WHERE prefix = ?", (prefix,))
    print(f"Removed project: {prefix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
