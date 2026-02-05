"""CLI commands for Debussy."""

import os
import subprocess
from datetime import datetime

from .config import YOLO_MODE, SESSION_NAME


def log(msg: str, icon: str = "•"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} {icon} {msg}")


def cmd_start(args):
    """Start the system with tmux."""
    subprocess.run(["tmux", "kill-session", "-t", SESSION_NAME],
                   capture_output=True, check=False)

    subprocess.run([
        "tmux", "new-session", "-d", "-s", SESSION_NAME, "-n", "main"
    ], check=True)

    t = f"{SESSION_NAME}:main"
    subprocess.run(["tmux", "split-window", "-h", "-p", "66", "-t", t], check=True)
    subprocess.run(["tmux", "split-window", "-h", "-p", "50", "-t", f"{t}.1"], check=True)
    subprocess.run(["tmux", "split-window", "-v", "-p", "50", "-t", f"{t}.0"], check=True)
    subprocess.run(["tmux", "split-window", "-v", "-p", "50", "-t", f"{t}.3"], check=True)

    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.0", claude_cmd, "C-m"], check=True)
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.1", "", ""], check=True)
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.2", "watch -n 5 'debussy status'", "C-m"], check=True)
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.3", "debussy watch", "C-m"], check=True)
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.4", "watch -n 10 'git log --oneline -20'", "C-m"], check=True)

    conductor_prompt = """You are @conductor - the orchestrator. NEVER write code yourself.

YOUR JOB:
1. Receive requirements from user
2. Ask clarifying questions if unclear
3. Create tasks with: bd create "title" --status planning
4. When done planning, release tasks: bd update <id> --status open
5. Monitor progress with: debussy status

CREATING TASKS (planning phase):
bd create "Implement user login" --status planning
bd create "Add logout button" --status planning

RELEASING TASKS (when planning complete):
bd update bd-001 --status open
bd update bd-002 --status open

PIPELINE (automatic after release):
planning → open → developer → reviewing → reviewer → testing → tester → merging → integrator → acceptance → tester → done

Watcher spawns agents when status is 'open'. Max 3 developers/testers/reviewers run in parallel.

NEVER run npm/npx/pip/cargo. NEVER use Write/Edit tools. NEVER write code."""

    if args.requirement:
        prompt = f"{conductor_prompt}\n\nUser requirement: {args.requirement}"
    else:
        prompt = conductor_prompt

    import time
    time.sleep(6)
    subprocess.run([
        "tmux", "send-keys", "-l", "-t", f"{SESSION_NAME}:main.0",
        prompt
    ], check=True)
    time.sleep(0.5)
    subprocess.run([
        "tmux", "send-keys", "-t", f"{SESSION_NAME}:main.0",
        "Enter"
    ], check=True)

    t = f"{SESSION_NAME}:main"
    subprocess.run(["tmux", "select-pane", "-t", f"{t}.0", "-T", "conductor"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{t}.1", "-T", "cmd"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{t}.2", "-T", "status"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{t}.3", "-T", "watcher"], check=True)
    subprocess.run(["tmux", "select-pane", "-t", f"{t}.4", "-T", "git"], check=True)

    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-status", "top"], check=True)
    subprocess.run(["tmux", "set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} "], check=True)

    subprocess.run(["tmux", "select-pane", "-t", f"{t}.0"], check=True)

    print("🎼 Debussy started")
    print("")
    print("Layout:")
    print("  ┌──────────┬──────────┬──────────┐")
    print("  │conductor │          │ watcher  │")
    print("  ├──────────┤  status  ├──────────┤")
    print("  │   cmd    │          │   git    │")
    print("  └──────────┴──────────┴──────────┘")
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    """Run the watcher."""
    from .watcher import Watcher
    Watcher().run()


def _get_tasks_by_status(status):
    result = subprocess.run(["bd", "list", "--status", status], capture_output=True, text=True)
    if not result.stdout.strip():
        return []
    return [t for t in result.stdout.strip().split('\n') if t.strip()]


def _print_section(icon, title, tasks, empty_msg=None):
    if not tasks:
        if empty_msg:
            print(f"{icon} {title}: {empty_msg}")
        return
    print(f"{icon} {title} ({len(tasks)})")
    for t in tasks:
        print(f"   {t}")
    print()


def _print_raw(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
        print()


def cmd_status(args):
    """Show system status."""
    print("\n=== DEBUSSY STATUS ===\n")

    planning = _get_tasks_by_status("planning")
    if planning:
        print(f"📋 PLANNING ({len(planning)})")
        for t in planning:
            print(f"   {t}")
        print()

    pipeline_statuses = [
        ("open", "→ developer"),
        ("testing", "→ tester"),
        ("reviewing", "→ reviewer"),
        ("merging", "→ integrator"),
        ("acceptance", "→ tester"),
    ]

    active = []
    for status, role in pipeline_statuses:
        tasks = _get_tasks_by_status(status)
        for t in tasks:
            active.append(f"[{status} {role}] {t}")

    if active:
        print(f"▶ ACTIVE ({len(active)})")
        for a in active:
            print(f"   {a}")
        print()
    else:
        print("▶ ACTIVE: none")
        print()

    _print_raw(["bd", "blocked"])

    done_tasks = _get_tasks_by_status("done")
    if done_tasks:
        print(f"✓ DONE ({len(done_tasks)})")
        for t in done_tasks:
            print(f"   {t}")
        print()

    result = subprocess.run(["git", "branch", "--list", "feature/*"], capture_output=True, text=True)
    if result.stdout.strip():
        branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
        print(f"🌿 BRANCHES ({len(branches)})")
        for b in branches:
            print(f"   {b}")
        print()


def cmd_upgrade(args):
    """Upgrade debussy to latest version."""
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
    """Upgrade and restart the session."""
    import tempfile

    if args.upgrade:
        result = cmd_upgrade(args)
        if result != 0:
            return result

    script = f"""#!/bin/bash
sleep 1
tmux kill-session -t {SESSION_NAME} 2>/dev/null
sleep 1
cd {os.getcwd()}
debussy start
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(script)
        script_path = f.name

    os.chmod(script_path, 0o755)
    subprocess.Popen(["nohup", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Restarting in background...", "🔄")


def cmd_config(args):
    """View or set config."""
    from .config import get_config, set_config

    if args.key and args.value is not None:
        set_config(args.key, args.value)
        log(f"Set {args.key} = {args.value}", "✓")
    elif args.key:
        cfg = get_config()
        val = cfg.get(args.key, "not set")
        print(f"{args.key} = {val}")
    else:
        cfg = get_config()
        print("Current config:")
        for k, v in cfg.items():
            print(f"  {k} = {v}")


PIPELINE_STATUSES = "planning,testing,reviewing,merging,acceptance,done"


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
    """Initialize beads with debussy pipeline statuses."""
    from pathlib import Path

    if not Path(".beads").exists():
        result = subprocess.run(["bd", "init"], capture_output=True)
        if result.returncode != 0:
            log("Failed to init beads", "✗")
            return 1
        log("Initialized beads", "✓")

    _configure_beads_statuses()


def cmd_clear(args):
    """Clear all beads and runtime config."""
    import shutil
    from pathlib import Path

    beads_dir = Path(".beads")
    debussy_dir = Path(".debussy")

    if beads_dir.exists():
        shutil.rmtree(beads_dir)
        log("Removed .beads", "🗑")

    if debussy_dir.exists():
        shutil.rmtree(debussy_dir)
        log("Removed .debussy", "🗑")

    result = subprocess.run(["bd", "init"], capture_output=True)
    if result.returncode != 0:
        log("Failed to init beads", "✗")
        return 1
    log("Initialized fresh beads", "✓")

    _configure_beads_statuses()


def cmd_logs(args):
    """View agent logs."""
    from pathlib import Path

    logs_dir = Path(".debussy/logs")
    if not logs_dir.exists():
        print("No logs yet. Start the watcher first.")
        return

    if args.agent:
        log_file = logs_dir / f"{args.agent}.log"
        if not log_file.exists():
            matches = list(logs_dir.glob(f"*{args.agent}*.log"))
            if matches:
                log_file = matches[0]
            else:
                print(f"No log found for '{args.agent}'")
                print("Available:", [f.stem for f in logs_dir.glob("*.log")])
                return
        if args.follow:
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            subprocess.run(["tail", "-100", str(log_file)])
    else:
        logs = list(logs_dir.glob("*.log"))
        if not logs:
            print("No agent logs yet.")
            return
        print("Agent logs:")
        for log_file in sorted(logs, key=lambda f: f.stat().st_mtime, reverse=True):
            size = log_file.stat().st_size
            print(f"  {log_file.stem}: {size} bytes")
        print("\nUsage: dbs logs <agent-name> [-f]")
