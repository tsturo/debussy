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

    return 1


if __name__ == "__main__":
    sys.exit(main())
