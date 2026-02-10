"""CLI commands for Debussy."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from .config import (
    CLAUDE_STARTUP_DELAY, COMMENT_TRUNCATE_LEN, PIPELINE_STATUSES,
    SESSION_NAME, STATUS_TO_ROLE, YOLO_MODE, get_config, log, parse_value,
    set_config,
)

CONDUCTOR_PROMPT = """You are @conductor - the orchestrator. NEVER write code yourself.

YOUR JOB:
1. Receive requirements from user
2. Ask clarifying questions if unclear
3. Create a feature branch FIRST: git checkout -b feature/<short-name> && git push -u origin feature/<short-name>
4. Register the branch: debussy config base_branch feature/<short-name>
5. Create tasks with: bd create "title" --status planning
6. When done planning, release tasks: bd update <id> --status open
7. Monitor progress with: debussy status

BRANCHING (MANDATORY first step before creating tasks):
git checkout -b feature/user-auth           # create conductor's feature branch
git push -u origin feature/user-auth        # push to remote
debussy config base_branch feature/user-auth  # register as base branch

Developers will branch off YOUR feature branch. Integrator merges back into YOUR branch.
Merging to master is done ONLY by the user manually. NEVER merge to master.

CREATING TASKS (planning phase):
bd create "Implement user login" --status planning
bd create "Add logout button" --status planning

RELEASING TASKS (when planning complete):
bd update bd-001 --status open            # development task
bd update bd-002 --status investigating   # investigation/research task

PIPELINES:
Development: planning → open → developer → reviewing → testing → merging → acceptance → done
Investigation: planning → investigating (parallel) → consolidating → dev tasks created → done

PARALLEL INVESTIGATION:
bd create "Investigate area A" --status investigating          # → bd-001
bd create "Investigate area B" --status investigating          # → bd-002
bd create "Consolidate findings" --deps "bd-001,bd-002" --status consolidating

Watcher spawns agents automatically. Max 3 developers/investigators/testers/reviewers in parallel.

NEVER run npm/npx/pip/cargo. NEVER use Write/Edit tools. NEVER write code.
NEVER merge to master — that is done only by the user."""


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
    import time

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


def _get_tasks_by_status(status: str) -> list[str]:
    result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
    if not result.stdout.strip():
        return []
    return [t for t in result.stdout.strip().split('\n') if t.strip()]


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


def cmd_status(args):
    print("\n=== DEBUSSY STATUS ===\n")

    running = _get_running_agents()

    active = []
    for status, role_label in STATUS_TO_ROLE.items():
        tasks = _get_tasks_by_status(status)
        for t in tasks:
            bead_id = t.split()[0] if t else ""
            if bead_id in running:
                agent = running[bead_id]["agent"]
                active.append((f"[{status}] {t} ← {agent} 🔄", bead_id))
            else:
                active.append((f"[{status} → {role_label}] {t}", bead_id))

    if active:
        print(f"▶ ACTIVE ({len(active)})")
        for line, bead_id in active:
            print(f"   {line}")
            try:
                comments = _get_bead_comments(bead_id)
                if comments:
                    print(f"      💬 {comments[-1][:COMMENT_TRUNCATE_LEN]}")
            except Exception:
                pass
        print()
    else:
        print("▶ ACTIVE: none")
        print()

    result = subprocess.run(["bd", "blocked"], capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
        print()

    done_tasks = _get_tasks_by_status("done")
    if done_tasks:
        print(f"✓ DONE ({len(done_tasks)})")
        for t in done_tasks:
            print(f"   {t}")
        print()
    else:
        print("✓ DONE: none")
        print()


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


def _configure_beads_statuses():
    result = subprocess.run(
        ["bd", "config", "set", "status.custom", PIPELINE_STATUSES],
        capture_output=True
    )
    if result.returncode == 0:
        log("Configured pipeline statuses", "✓")
    else:
        log("Failed to configure statuses", "✗")


def cmd_init(args):
    if not Path(".beads").exists():
        result = subprocess.run(["bd", "init"], capture_output=True)
        if result.returncode != 0:
            log("Failed to init beads", "✗")
            return 1
        log("Initialized beads", "✓")

    _configure_beads_statuses()


def _backup_beads() -> Path | None:
    from datetime import datetime

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

    _configure_beads_statuses()


def cmd_debug(args):
    print("=== DEBUSSY DEBUG ===\n")

    print("Checking custom statuses...")
    result = subprocess.run(["bd", "config", "get", "status.custom"], capture_output=True, text=True)
    if result.stdout.strip():
        print(f"  Custom statuses: {result.stdout.strip()}")
    else:
        print("  ⚠️  No custom statuses configured! Run: dbs init")
    print()

    print("Checking pipeline statuses...")
    for status in STATUS_TO_ROLE:
        result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
        count = len([l for l in result.stdout.strip().split('\n') if l.strip()]) if result.stdout.strip() else 0
        print(f"  {status}: {count} tasks")
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n')[:3]:
                print(f"    → {line}")
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
        print("  ⚠️  .debussy directory doesn't exist")
    print()
