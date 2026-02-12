"""CLI commands for Debussy."""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .config import (
    CLAUDE_STARTUP_DELAY, COMMENT_TRUNCATE_LEN,
    SESSION_NAME, STAGE_TO_ROLE, YOLO_MODE, get_config, log, parse_value,
    set_config,
)
from .prompts import CONDUCTOR_PROMPT
from .worktree import remove_worktree, remove_all_worktrees


def _preflight_check() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log("Not a git repository", "✗")
        return False
    result = subprocess.run(
        ["git", "remote"], capture_output=True, text=True,
    )
    if "origin" not in result.stdout.split():
        log("No 'origin' remote configured. Debussy requires a git remote.", "✗")
        log("Add one with: git remote add origin <url>", "")
        return False
    return True


def _run_tmux(*args, check=True):
    return subprocess.run(["tmux", *args], capture_output=True, check=check)


def _send_keys(target: str, keys: str, literal: bool = False):
    cmd = ["tmux", "send-keys"]
    if literal:
        cmd.append("-l")
    cmd.extend(["-t", target, keys])
    if not literal:
        cmd.append("C-m")
    subprocess.run(cmd, check=True)


def _create_tmux_layout():
    _run_tmux("kill-session", "-t", SESSION_NAME, check=False)
    _run_tmux("new-session", "-d", "-s", SESSION_NAME, "-n", "main")

    t = f"{SESSION_NAME}:main"
    _run_tmux("split-window", "-h", "-p", "33", "-t", t)
    _run_tmux("split-window", "-h", "-p", "50", "-t", f"{t}.0")
    _run_tmux("split-window", "-v", "-p", "50", "-t", f"{t}.0")

    Path(".debussy").mkdir(parents=True, exist_ok=True)

    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    _send_keys(f"{t}.0", claude_cmd)
    _send_keys(f"{t}.2", "watch -n 5 'debussy status'")
    _send_keys(f"{t}.3", "debussy watch")


def _label_panes():
    t = f"{SESSION_NAME}:main"
    for idx, title in enumerate(["conductor", "cmd", "status", "watcher"]):
        _run_tmux("select-pane", "-t", f"{t}.{idx}", "-T", title)
    _run_tmux("set-option", "-t", SESSION_NAME, "pane-border-status", "top")
    _run_tmux("set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} ")
    _run_tmux("select-pane", "-t", f"{t}.0")


def _send_conductor_prompt(requirement: str | None):
    prompt = CONDUCTOR_PROMPT
    if requirement:
        prompt = f"{prompt}\n\nUser requirement: {requirement}"

    target = f"{SESSION_NAME}:main.0"
    time.sleep(CLAUDE_STARTUP_DELAY)
    _send_keys(target, prompt, literal=True)
    time.sleep(0.5)
    subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], check=True)


def cmd_start(args):
    if not _preflight_check():
        return 1
    _create_tmux_layout()
    _send_conductor_prompt(getattr(args, "requirement", None))
    _label_panes()

    print("🎼 Debussy started")
    print("")
    print("Layout:")
    print("  ┌──────────┬──────────┬─────────┐")
    print("  │conductor │          │         │")
    print("  ├──────────┤  status  │ watcher │")
    print("  │   cmd    │          │         │")
    print("  └──────────┴──────────┴─────────┘")
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    if not _preflight_check():
        return 1
    from .watcher import Watcher
    Watcher().run()


def _get_all_beads() -> list[dict]:
    beads = {}
    for status in ("open", "in_progress", "closed", "blocked"):
        try:
            result = subprocess.run(
                ["bd", "list", "--status", status, "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout)
            if isinstance(data, list):
                for bead in data:
                    bead_id = bead.get("id")
                    if bead_id:
                        beads[bead_id] = bead
        except Exception:
            continue
    return list(beads.values())


def _get_running_agents() -> dict:
    state_file = Path(".debussy/watcher_state.json")
    if not state_file.exists():
        return {}
    try:
        with open(state_file) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_bead_comments(bead_id: str) -> list[str]:
    try:
        result = subprocess.run(
            ["bd", "show", bead_id],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
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
                        print(f"      💬 {comments[-1][:COMMENT_TRUNCATE_LEN]}")
                except Exception:
                    pass
    else:
        print(f"{label}: none")
    print()


def _waiting_on(bead: dict, all_beads_by_id: dict) -> list[str]:
    waiting = []
    for dep in bead.get("dependencies", []):
        dep_id = dep.get("depends_on_id") or dep.get("id")
        dep_status = dep.get("status") or all_beads_by_id.get(dep_id, {}).get("status")
        if dep_id and dep_status != "closed":
            waiting.append(dep_id)
    return waiting


def _print_blocked_tree(blocked: list, all_beads_by_id: dict):
    blocked_ids = {bead_id for _, bead_id in blocked}
    lines_by_id = {bead_id: line for line, bead_id in blocked}

    children: dict[str, list[str]] = {}
    roots = []
    for _, bead_id in blocked:
        bead = all_beads_by_id.get(bead_id, {})
        blocked_parents = [d for d in _waiting_on(bead, all_beads_by_id) if d in blocked_ids]
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
        prefix = "   " + "  " * indent + ("└ " if indent > 0 else "")
        print(f"{prefix}{lines_by_id.get(bead_id, bead_id)}")
        for child in children.get(bead_id, []):
            _print_node(child, indent + 1)

    print(f"⊘ BLOCKED ({len(blocked)})")
    for root in roots:
        _print_node(root, 0)
    for _, bead_id in blocked:
        if bead_id not in printed:
            _print_node(bead_id, 0)
    print()


def _dep_summary(bead: dict, all_beads_by_id: dict) -> str:
    deps = bead.get("dependencies", [])
    if not deps:
        return ""
    waiting = []
    for dep in deps:
        dep_id = dep.get("depends_on_id") or dep.get("id")
        if not dep_id:
            continue
        status = dep.get("status") or all_beads_by_id.get(dep_id, {}).get("status")
        if status != "closed":
            waiting.append(dep_id)
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
        agent_str = f" ← {running[bead_id]['agent']} 🔄"

    if status == "closed":
        return "done", f"{bead_id} {title}", bead_id

    if status == "blocked":
        dep_info = _dep_summary(bead, all_beads_by_id)
        return "blocked", f"[blocked] {bead_id} {title}{dep_info}", bead_id

    dep_info = _dep_summary(bead, all_beads_by_id)
    if dep_info:
        stage_info = f" {stages[0]}" if stages else ""
        return "blocked", f"[waiting{stage_info}] {bead_id} {title}{dep_info}", bead_id

    if status == "in_progress":
        stage_info = f" {stages[0]}" if stages else ""
        return "active", f"[in_progress{stage_info}] {bead_id} {title}{agent_str}", bead_id

    if stages:
        stage = stages[0]
        role = STAGE_TO_ROLE.get(stage, "?")
        return "active", f"[{stage} → {role}] {bead_id} {title}{agent_str}", bead_id

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
    except Exception:
        return []


def cmd_status(args):
    print("\n=== DEBUSSY STATUS ===\n")

    running = _get_running_agents()
    all_beads = _get_all_beads()
    all_beads_by_id = {b.get("id"): b for b in all_beads if b.get("id")}

    active = []
    backlog = []
    blocked = []
    done = []

    buckets = {
        "active": active,
        "backlog": backlog,
        "blocked": blocked,
        "done": done,
    }

    for bead in all_beads:
        bucket, line, bead_id = _format_bead(bead, running, all_beads_by_id)
        buckets[bucket].append((line, bead_id))

    _print_section("▶ ACTIVE", active, show_comments=True)
    _print_section("◻ BACKLOG", backlog)
    if blocked:
        _print_blocked_tree(blocked, all_beads_by_id)
    _print_section("✓ DONE", done)

    branches = _get_branches()
    if branches:
        print(f"⎇ BRANCHES ({len(branches)})")
        for branch in branches:
            print(f"   {branch}")
        print()


def cmd_upgrade(args):
    from . import __version__
    log(f"Current version: {__version__}", "📦")
    log("Upgrading debussy...", "⬆️")
    result = subprocess.run([
        "pipx", "install", "--force",
        "git+https://github.com/tsturo/debussy.git"
    ])
    if result.returncode == 0:
        new_ver = subprocess.run(
            ["debussy", "--version"],
            capture_output=True, text=True
        )
        log(f"Upgraded to: {new_ver.stdout.strip()}", "✓")
    else:
        log("Upgrade failed", "✗")
    return result.returncode


def cmd_restart(args):
    if args.upgrade:
        result = cmd_upgrade(args)
        if result != 0:
            return result

    cmd_pause(args)

    cwd = os.getcwd()
    subprocess.Popen(
        ["bash", "-c",
         f"sleep 1 && tmux kill-session -t {SESSION_NAME} 2>/dev/null && sleep 1 && cd {cwd} && debussy start"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    log("Restarting in background...", "🔄")


def cmd_config(args):
    if args.key and args.value is not None:
        value = parse_value(args.value)
        set_config(args.key, value)
        log(f"Set {args.key} = {value}", "✓")
    elif args.key:
        cfg = get_config()
        val = cfg.get(args.key, "not set")
        print(f"{args.key} = {val}")
    else:
        cfg = get_config()
        print("Current config:")
        for k, v in cfg.items():
            print(f"  {k} = {v}")


def _backup_beads() -> Path | None:
    beads_dir = Path(".beads")
    if not beads_dir.exists():
        return None

    backup_dir = Path(".debussy/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"beads_{timestamp}"
    shutil.copytree(beads_dir, backup_path)
    return backup_path


def cmd_backup(args):
    backup_path = _backup_beads()
    if backup_path:
        log(f"Backed up to {backup_path}", "✓")
    else:
        log("No .beads directory to backup", "⚠️")


def cmd_clear(args):
    beads_dir = Path(".beads")
    debussy_dir = Path(".debussy")

    if beads_dir.exists() and not getattr(args, 'force', False):
        result = subprocess.run(["bd", "list"], capture_output=True, text=True)
        task_count = len([l for l in result.stdout.strip().split('\n') if l.strip()]) if result.stdout.strip() else 0
        if task_count > 0:
            print(f"⚠️  This will delete {task_count} tasks!")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                log("Aborted", "✗")
                return 1

    if beads_dir.exists():
        backup_path = _backup_beads()
        if backup_path:
            log(f"Backed up to {backup_path}", "💾")
        shutil.rmtree(beads_dir)
        log("Removed .beads", "🗑")

    try:
        remove_all_worktrees()
        log("Removed all worktrees", "🧹")
    except Exception:
        pass

    if debussy_dir.exists():
        for item in debussy_dir.iterdir():
            if item.name != "backups":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        log("Cleared .debussy (kept backups)", "🗑")

    result = subprocess.run(["bd", "init"], capture_output=True)
    if result.returncode != 0:
        log("Failed to init beads", "✗")
        return 1
    log("Initialized fresh beads", "✓")


def _stop_watcher():
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{SESSION_NAME}:main.3", "C-c"],
        capture_output=True,
    )


def _kill_agent(agent: dict, agent_name: str):
    if agent.get("tmux"):
        subprocess.run(
            ["tmux", "kill-window", "-t", f"{SESSION_NAME}:{agent_name}"],
            capture_output=True,
        )


def _get_bead_status(bead_id: str) -> str | None:
    try:
        result = subprocess.run(
            ["bd", "show", bead_id, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and data:
            return data[0].get("status")
    except Exception:
        pass
    return None


def _reset_bead_to_open(bead_id: str):
    status = _get_bead_status(bead_id)
    if status and status == "in_progress":
        subprocess.run(
            ["bd", "comment", bead_id, "Paused by debussy pause"],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            ["bd", "update", bead_id, "--status", "open"],
            capture_output=True, timeout=5,
        )
        log(f"Reset {bead_id} ({status} → open)", "⏸")


def _delete_orphan_branches(paused_beads: set[str]):
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "feature/bd-*"],
            capture_output=True, text=True,
        )
        for line in result.stdout.strip().split('\n'):
            branch = line.strip().lstrip("* ")
            if not branch:
                continue
            bead_id = branch.replace("feature/", "")
            if bead_id in paused_beads:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    capture_output=True,
                )
                log(f"Deleted branch {branch}", "🗑")
    except Exception as e:
        log(f"Failed to clean branches: {e}", "⚠️")


def cmd_pause(args):
    state_file = Path(".debussy/watcher_state.json")

    _stop_watcher()

    state = {}
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
        except Exception:
            pass

    paused_beads = set()
    for bead_id, agent in state.items():
        agent_name = agent.get("agent", "")
        _kill_agent(agent, agent_name)
        log(f"Killed {agent_name}", "🛑")
        if agent.get("worktree_path"):
            try:
                remove_worktree(agent_name)
                log(f"Removed worktree for {agent_name}", "🧹")
            except Exception:
                pass
        _reset_bead_to_open(bead_id)
        paused_beads.add(bead_id)

    _delete_orphan_branches(paused_beads)

    if state_file.exists():
        state_file.unlink()

    log("Pipeline paused", "⏸")

    if getattr(args, "restart", False):
        cmd_start(args)


def cmd_debug(args):
    print("=== DEBUSSY DEBUG ===\n")

    all_beads = _get_all_beads()

    by_status = {}
    by_stage = {}
    for bead in all_beads:
        status = bead.get("status", "unknown")
        by_status.setdefault(status, []).append(bead)
        for label in bead.get("labels", []):
            if label.startswith("stage:"):
                by_stage.setdefault(label, []).append(bead)

    print("By status:")
    for status in ("open", "in_progress", "closed", "blocked"):
        beads = by_status.get(status, [])
        print(f"  {status}: {len(beads)}")
    print()

    print("By stage label:")
    for stage in STAGE_TO_ROLE:
        beads = by_stage.get(stage, [])
        print(f"  {stage}: {len(beads)}")
        for bead in beads[:3]:
            print(f"    → {bead.get('id')} {bead.get('title', '')}")
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


STAGE_SHORT = {
    "stage:development": "dev",
    "stage:reviewing": "rev",
    "stage:merging": "merge",
    "stage:acceptance": "accept",
    "stage:investigating": "inv",
    "stage:consolidating": "cons",
}


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    return f"{seconds / 3600:.1f}h"


def cmd_metrics(args):
    events_file = Path(".debussy/pipeline_events.jsonl")
    if not events_file.exists():
        print("No pipeline events recorded yet.")
        return

    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue

    if not events:
        print("No pipeline events recorded yet.")
        return

    print("\n=== PIPELINE METRICS ===\n")

    bead_events: dict[str, list] = {}
    for e in events:
        bead_events.setdefault(e["bead"], []).append(e)

    stage_durations: dict[str, list[float]] = {}
    total_rejections = 0
    total_timeouts = 0

    print("Per-bead:")
    for bead_id, bevents in bead_events.items():
        bevents.sort(key=lambda e: e["ts"])
        stages = []
        stage_counts: dict[str, int] = {}
        current_stage = None
        stage_start = None

        for e in bevents:
            if e["event"] == "spawn":
                current_stage = e.get("stage")
                stage_start = e["ts"]
            elif e["event"] == "advance":
                if stage_start and current_stage:
                    dur = e["ts"] - stage_start
                    short = STAGE_SHORT.get(current_stage, current_stage)
                    count = stage_counts.get(current_stage, 0) + 1
                    stage_counts[current_stage] = count
                    count_str = f"{count}x " if count > 1 else ""
                    stages.append(f"{short}({count_str}{_fmt_duration(dur)})")
                    stage_durations.setdefault(current_stage, []).append(dur)
                current_stage = e.get("to")
                stage_start = e["ts"]
            elif e["event"] == "reject":
                total_rejections += 1
                if stage_start and current_stage:
                    dur = e["ts"] - stage_start
                    short = STAGE_SHORT.get(current_stage, current_stage)
                    stages.append(f"{short}({_fmt_duration(dur)}!)")
                    stage_durations.setdefault(current_stage, []).append(dur)
                current_stage = e.get("to")
                stage_start = e["ts"]
            elif e["event"] == "timeout":
                total_timeouts += 1
            elif e["event"] == "close":
                if stage_start and current_stage:
                    dur = e["ts"] - stage_start
                    short = STAGE_SHORT.get(current_stage, current_stage)
                    count = stage_counts.get(current_stage, 0) + 1
                    count_str = f"{count}x " if count > 1 else ""
                    stages.append(f"{short}({count_str}{_fmt_duration(dur)})")
                    stage_durations.setdefault(current_stage, []).append(dur)
                stages.append("done")

        total = bevents[-1]["ts"] - bevents[0]["ts"] if len(bevents) > 1 else 0
        trail = " → ".join(stages) if stages else "started"
        print(f"  {bead_id}  {trail}  [{_fmt_duration(total)}]")

    print()
    if stage_durations:
        print("Stage averages:")
        for stage in ("stage:development", "stage:reviewing",
                       "stage:merging", "stage:acceptance"):
            durs = stage_durations.get(stage, [])
            if durs:
                avg = sum(durs) / len(durs)
                print(f"  {STAGE_SHORT.get(stage, stage):8s} avg {_fmt_duration(avg):>5s}  ({len(durs)} passes)")
        print()

    if total_rejections or total_timeouts:
        print(f"Issues: {total_rejections} rejections, {total_timeouts} timeouts")
        print()
