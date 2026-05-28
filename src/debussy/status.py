"""Runtime info helpers for the kanban board."""

import json
import subprocess
import time

from .agent import repo_root
from .config import get_config


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    return f"{seconds / 3600:.1f}h"


def get_running_agents() -> dict:
    try:
        state_file = repo_root() / ".debussy" / "watcher_state.json"
    except RuntimeError:
        return {}
    if not state_file.exists():
        return {}
    try:
        with open(state_file) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


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
            dur = _fmt_duration(now - started) if started else "?"
            print(f"  {agent} ({role}) → {task_id}  [{dur}]")
        print()

    branches = _get_branches()
    if branches:
        print(f"Branches ({len(branches)}):")
        for branch in branches:
            print(f"  {branch}")
        print()
