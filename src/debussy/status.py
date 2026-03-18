"""Status and debug display for Debussy."""

import json
import subprocess
import time
from pathlib import Path

from .config import (
    COMMENT_TRUNCATE_LEN, STAGE_DONE, STAGE_TO_ROLE,
    STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    get_config,
)
from .metrics import fmt_duration
from .takt import get_db, get_log, get_unresolved_deps


def get_running_agents() -> dict:
    state_file = Path(".debussy/watcher_state.json")
    if not state_file.exists():
        return {}
    try:
        with open(state_file) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _get_task_comments(task_id: str) -> list[str]:
    try:
        with get_db() as db:
            entries = get_log(db, task_id, type="comment")
        return [e.get("message", "") for e in entries if e.get("message")]
    except Exception:
        return []


def _print_section(label: str, items: list, show_comments: bool = False):
    if items:
        print(f"{label} ({len(items)})")
        for line, task_id in items:
            print(f"   {line}")
            if show_comments:
                try:
                    comments = _get_task_comments(task_id)
                    if comments:
                        print(f"      \U0001f4ac {comments[-1][:COMMENT_TRUNCATE_LEN]}")
                except Exception:
                    pass
    else:
        print(f"{label}: none")
    print()


def _print_blocked_tree(blocked: list, all_tasks_by_id: dict):
    blocked_ids = {task_id for _, task_id in blocked}
    lines_by_id = {task_id: line for line, task_id in blocked}

    children: dict[str, list[str]] = {}
    roots = []
    for _, task_id in blocked:
        task = all_tasks_by_id.get(task_id, {})
        with get_db() as db:
            unresolved = get_unresolved_deps(db, task_id) if task_id else []
        blocked_parents = [d for d in unresolved if d in blocked_ids]
        if blocked_parents:
            for parent in blocked_parents:
                children.setdefault(parent, []).append(task_id)
        else:
            roots.append(task_id)

    printed = set()

    def _print_node(task_id: str, indent: int):
        if task_id in printed:
            return
        printed.add(task_id)
        prefix = "   " + "  " * indent + ("\u2514 " if indent > 0 else "")
        print(f"{prefix}{lines_by_id.get(task_id, task_id)}")
        for child in children.get(task_id, []):
            _print_node(child, indent + 1)

    print(f"\u2298 BLOCKED ({len(blocked)})")
    for root in roots:
        _print_node(root, 0)
    for _, task_id in blocked:
        if task_id not in printed:
            _print_node(task_id, 0)
    print()


def _dep_summary(task_id: str) -> str:
    with get_db() as db:
        waiting = get_unresolved_deps(db, task_id)
    if not waiting:
        return ""
    return f" (waiting: {', '.join(waiting)})"


def _format_task(task: dict, running: dict, all_tasks_by_id: dict) -> tuple[str, str, str]:
    task_id = task.get("id", "")
    title = task.get("title", "")
    status = task.get("status", "")
    stage = task.get("stage", "")

    agent_str = ""
    if task_id in running:
        agent_str = f" \u2190 {running[task_id]['agent']} \U0001f504"

    if stage == STAGE_DONE:
        return "done", f"{task_id} {title}", task_id

    if status == STATUS_BLOCKED:
        dep_info = _dep_summary(task_id)
        return "blocked", f"[blocked] {task_id} {title}{dep_info}", task_id

    dep_info = _dep_summary(task_id)
    if dep_info:
        stage_info = f" {stage}" if stage else ""
        return "blocked", f"[waiting{stage_info}] {task_id} {title}{dep_info}", task_id

    if status == STATUS_ACTIVE:
        stage_info = f" {stage}" if stage else ""
        return "active", f"[active{stage_info}] {task_id} {title}{agent_str}", task_id

    if stage in STAGE_TO_ROLE:
        role = STAGE_TO_ROLE.get(stage, "?")
        return "active", f"[{stage} \u2192 {role}] {task_id} {title}{agent_str}", task_id

    return "backlog", f"[pending] {task_id} {title}", task_id


def _get_branches() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "feature/*"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        current = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        current_branch = current.stdout.strip()
        branches = []
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")
            if branch:
                marker = " *" if branch == current_branch else ""
                branches.append(f"{branch}{marker}")
        return branches
    except (subprocess.SubprocessError, OSError):
        return []


def print_runtime_info(running):
    now = time.time()
    cfg = get_config()
    base = cfg.get("base_branch", "not set")
    max_agents = cfg.get("max_total_agents", 8)

    print(f"  base: {base}  agents: {len(running)}/{max_agents}")
    print()

    if running:
        print("Agents:")
        for task_id, info in running.items():
            agent = info.get("agent", "?")
            role = info.get("role", "?")
            started = info.get("started_at")
            dur = fmt_duration(now - started) if started else "?"
            print(f"  {agent} ({role}) \u2192 {task_id}  [{dur}]")
        print()

    branches = _get_branches()
    if branches:
        print(f"Branches ({len(branches)}):")
        for branch in branches:
            print(f"  {branch}")
        print()
