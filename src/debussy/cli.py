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
    from .watcher import Watcher
    Watcher().run()


def _get_beads_by_label(label: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["bd", "list", "--status", "open", "--label", label, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_beads_by_status(status: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["bd", "list", "--status", status, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else []
    except Exception:
        return []


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


def cmd_status(args):
    print("\n=== DEBUSSY STATUS ===\n")

    running = _get_running_agents()

    active = []
    for bead in _get_beads_by_status("in_progress"):
        bead_id = bead.get("id", "")
        title = bead.get("title", "")
        if bead_id in running:
            agent = running[bead_id]["agent"]
            active.append((f"[in_progress] {bead_id} {title} ← {agent} 🔄", bead_id))
        else:
            active.append((f"[in_progress] {bead_id} {title}", bead_id))

    for stage, role_label in STAGE_TO_ROLE.items():
        for bead in _get_beads_by_label(stage):
            bead_id = bead.get("id", "")
            title = bead.get("title", "")
            if bead_id in running:
                agent = running[bead_id]["agent"]
                active.append((f"[{stage}] {bead_id} {title} ← {agent} 🔄", bead_id))
            else:
                active.append((f"[{stage} → {role_label}] {bead_id} {title}", bead_id))
    _print_section("▶ ACTIVE", active, show_comments=True)

    backlog = []
    for bead in _get_beads_by_status("open"):
        bead_id = bead.get("id", "")
        title = bead.get("title", "")
        labels = bead.get("labels", [])
        if any(l.startswith("stage:") for l in labels):
            continue
        backlog.append((f"[open] {bead_id} {title}", bead_id))
    _print_section("◻ BACKLOG", backlog)

    blocked = []
    for bead in _get_beads_by_status("blocked"):
        bead_id = bead.get("id", "")
        title = bead.get("title", "")
        blocked.append((f"[blocked] {bead_id} {title}", bead_id))
    if blocked:
        _print_section("⊘ BLOCKED", blocked)

    done = []
    for bead in _get_beads_by_status("closed"):
        bead_id = bead.get("id", "")
        title = bead.get("title", "")
        done.append((f"{bead_id} {title}", bead_id))
    _print_section("✓ DONE", done)


def cmd_upgrade(args):
    from . import __version__
    log(f"Current version: {__version__}", "📦")
    log("Upgrading debussy...", "⬆️")
    result = subprocess.run([
        "pipx", "runpip", "debussy", "install", "--upgrade",
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


def cmd_init(args):
    if not Path(".beads").exists():
        result = subprocess.run(["bd", "init"], capture_output=True)
        if result.returncode != 0:
            log("Failed to init beads", "✗")
            return 1
        log("Initialized beads", "✓")


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

    print("Checking pipeline stages...")
    for stage in STAGE_TO_ROLE:
        beads = _get_beads_by_label(stage)
        print(f"  {stage}: {len(beads)} tasks")
        for bead in beads[:3]:
            print(f"    → {bead.get('id')} {bead.get('title', '')}")

    print()
    for status in ("open", "in_progress", "closed", "blocked"):
        beads = _get_beads_by_status(status)
        print(f"  {status}: {len(beads)} tasks")
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
