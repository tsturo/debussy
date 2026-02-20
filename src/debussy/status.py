"""Status and debug display for Debussy."""

import json
import subprocess
import time
from pathlib import Path

from .bead_client import get_all_beads, get_unresolved_deps
from .config import (
    COMMENT_TRUNCATE_LEN, STAGE_TO_ROLE,
    STATUS_BLOCKED, STATUS_CLOSED, STATUS_IN_PROGRESS, STATUS_OPEN,
    get_config, log,
)
from .metrics import _fmt_duration


def _get_running_agents() -> dict:
    state_file = Path(".debussy/watcher_state.json")
    if not state_file.exists():
        return {}
    try:
        with open(state_file) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _get_bead_comments(bead_id: str) -> list[str]:
    try:
        result = subprocess.run(
            ["bd", "show", bead_id],
            capture_output=True, text=True, timeout=5
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if result.returncode != 0:
        return []
    comments = []
    in_comments = False
    for line in result.stdout.split('\n'):
        if line.startswith("Comments:") or line.startswith("## Comments"):
            in_comments = True
            continue
        if in_comments and line.strip() and not line.startswith("---"):
            comments.append(line.strip())
    return comments


def _print_section(label: str, items: list, show_comments: bool = False):
    if items:
        print(f"{label} ({len(items)})")
        for line, bead_id in items:
            print(f"   {line}")
            if show_comments:
                try:
                    comments = _get_bead_comments(bead_id)
                    if comments:
                        print(f"      \U0001f4ac {comments[-1][:COMMENT_TRUNCATE_LEN]}")
                except (subprocess.SubprocessError, OSError):
                    pass
    else:
        print(f"{label}: none")
    print()


def _print_blocked_tree(blocked: list, all_beads_by_id: dict):
    blocked_ids = {bead_id for _, bead_id in blocked}
    lines_by_id = {bead_id: line for line, bead_id in blocked}

    children: dict[str, list[str]] = {}
    roots = []
    for _, bead_id in blocked:
        bead = all_beads_by_id.get(bead_id, {})
        blocked_parents = [d for d in get_unresolved_deps(bead) if d in blocked_ids]
        if blocked_parents:
            for parent in blocked_parents:
                children.setdefault(parent, []).append(bead_id)
        else:
            roots.append(bead_id)

    printed = set()

    def _print_node(bead_id: str, indent: int):
        if bead_id in printed:
            return
        printed.add(bead_id)
        prefix = "   " + "  " * indent + ("\u2514 " if indent > 0 else "")
        print(f"{prefix}{lines_by_id.get(bead_id, bead_id)}")
        for child in children.get(bead_id, []):
            _print_node(child, indent + 1)

    print(f"\u2298 BLOCKED ({len(blocked)})")
    for root in roots:
        _print_node(root, 0)
    for _, bead_id in blocked:
        if bead_id not in printed:
            _print_node(bead_id, 0)
    print()


def _dep_summary(bead: dict) -> str:
    waiting = get_unresolved_deps(bead)
    if not waiting:
        return ""
    return f" (waiting: {', '.join(waiting)})"


def _format_bead(bead: dict, running: dict, all_beads_by_id: dict) -> tuple[str, str, str]:
    bead_id = bead.get("id", "")
    title = bead.get("title", "")
    status = bead.get("status", "")
    labels = bead.get("labels", [])
    stages = [l for l in labels if l.startswith("stage:")]

    agent_str = ""
    if bead_id in running:
        agent_str = f" \u2190 {running[bead_id]['agent']} \U0001f504"

    if status == STATUS_CLOSED:
        return "done", f"{bead_id} {title}", bead_id

    if status == STATUS_BLOCKED:
        dep_info = _dep_summary(bead)
        return "blocked", f"[blocked] {bead_id} {title}{dep_info}", bead_id

    dep_info = _dep_summary(bead)
    if dep_info:
        stage_info = f" {stages[0]}" if stages else ""
        return "blocked", f"[waiting{stage_info}] {bead_id} {title}{dep_info}", bead_id

    if status == STATUS_IN_PROGRESS:
        stage_info = f" {stages[0]}" if stages else ""
        return "active", f"[in_progress{stage_info}] {bead_id} {title}{agent_str}", bead_id

    if stages:
        stage = stages[0]
        role = STAGE_TO_ROLE.get(stage, "?")
        return "active", f"[{stage} \u2192 {role}] {bead_id} {title}{agent_str}", bead_id

    return "backlog", f"[open] {bead_id} {title}", bead_id


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


def _print_runtime_info(running):
    now = time.time()
    cfg = get_config()
    base = cfg.get("base_branch", "not set")
    max_agents = cfg.get("max_total_agents", 8)

    print(f"  base: {base}  agents: {len(running)}/{max_agents}")
    print()

    if running:
        print("Agents:")
        for bead_id, info in running.items():
            agent = info.get("agent", "?")
            role = info.get("role", "?")
            started = info.get("started_at")
            dur = _fmt_duration(now - started) if started else "?"
            print(f"  {agent} ({role}) \u2192 {bead_id}  [{dur}]")
        print()

    branches = _get_branches()
    if branches:
        print(f"Branches ({len(branches)}):")
        for branch in branches:
            print(f"  {branch}")
        print()


def _print_parent_progress(all_beads):
    by_parent = {}
    parent_beads = {}
    for bead in all_beads:
        pid = bead.get("parent_id")
        if pid:
            by_parent.setdefault(pid, []).append(bead)
        bead_id = bead.get("id")
        if bead_id:
            parent_beads[bead_id] = bead

    if not by_parent:
        return

    print("Features:")
    for pid, children in sorted(by_parent.items()):
        parent = parent_beads.get(pid)
        title = parent.get("title", pid) if parent else pid
        closed = sum(1 for c in children if c.get("status") == STATUS_CLOSED)
        total = len(children)
        check = " \u2713" if closed == total else ""
        print(f"  {title} ({closed}/{total}){check}")
    print()


def cmd_status(args):
    print("\n=== DEBUSSY STATUS ===\n")
    running = _get_running_agents()
    _print_runtime_info(running)
    all_beads = get_all_beads()
    _print_parent_progress(all_beads)


def cmd_debug(args):
    print("=== DEBUSSY DEBUG ===\n")

    all_beads = get_all_beads()

    by_status = {}
    by_stage = {}
    for bead in all_beads:
        status = bead.get("status", "unknown")
        by_status.setdefault(status, []).append(bead)
        for label in bead.get("labels", []):
            if label.startswith("stage:"):
                by_stage.setdefault(label, []).append(bead)

    print("By status:")
    for status in (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_CLOSED, STATUS_BLOCKED):
        beads = by_status.get(status, [])
        print(f"  {status}: {len(beads)}")
    print()

    print("By stage label:")
    for stage in STAGE_TO_ROLE:
        beads = by_stage.get(stage, [])
        print(f"  {stage}: {len(beads)}")
        for bead in beads[:3]:
            print(f"    \u2192 {bead.get('id')} {bead.get('title', '')}")
    print()

    print("Checking .debussy directory...")
    debussy_dir = Path(".debussy")
    if debussy_dir.exists():
        for item in debussy_dir.iterdir():
            if item.is_dir():
                count = len(list(item.iterdir()))
                print(f"  {item.name}/: {count} files")
            else:
                print(f"  {item.name}: {item.stat().st_size} bytes")
    else:
        print("  .debussy directory doesn't exist")
    print()
