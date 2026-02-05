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
    subprocess.run(["tmux", "send-keys", "-t", f"{t}.4", "watch -n 10 'git log --all --graph --oneline --decorate -30 && echo && git branch -a'", "C-m"], check=True)

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


def _get_running_agents():
    import json
    from pathlib import Path
    state_file = Path(".debussy/watcher_state.json")
    if not state_file.exists():
        return {}
    try:
        with open(state_file) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_bead_comments(bead_id: str) -> list[str]:
    result = subprocess.run(
        ["bd", "show", bead_id],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        return []
    comments = []
    in_comments = False
    for line in result.stdout.split('\n'):
        if line.startswith("Comments:") or line.startswith("## Comments"):
            in_comments = True
            continue
        if in_comments:
            if line.strip() and not line.startswith("---"):
                comments.append(line.strip())
    return comments


def cmd_status(args):
    """Show system status."""
    print("\n=== DEBUSSY STATUS ===\n")

    running = _get_running_agents()

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
            bead_id = t.split()[0] if t else ""
            if bead_id in running:
                agent = running[bead_id]["agent"]
                active.append((f"[{status}] {t} ← {agent} 🔄", bead_id))
            else:
                active.append((f"[{status} {role}] {t}", bead_id))

    if active:
        print(f"▶ ACTIVE ({len(active)})")
        for line, bead_id in active:
            print(f"   {line}")
            try:
                comments = _get_bead_comments(bead_id)
                if comments:
                    last_comment = comments[-1][:80]
                    print(f"      💬 {last_comment}")
            except Exception:
                pass
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
    else:
        print("✓ DONE: none")
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
        value = args.value
        if value.lower() in ("true", "1", "yes", "on"):
            value = True
        elif value.lower() in ("false", "0", "no", "off"):
            value = False
        else:
            try:
                value = int(value)
            except ValueError:
                pass
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


def _backup_beads():
    import shutil
    from pathlib import Path

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
    """Backup beads database."""
    backup_path = _backup_beads()
    if backup_path:
        log(f"Backed up to {backup_path}", "✓")
    else:
        log("No .beads directory to backup", "⚠️")


def cmd_clear(args):
    """Clear all beads and runtime config."""
    import shutil
    from pathlib import Path

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
    """Debug watcher pipeline detection."""
    from pathlib import Path

    print("=== DEBUSSY DEBUG ===\n")

    print("Checking custom statuses...")
    result = subprocess.run(["bd", "config", "get", "status.custom"], capture_output=True, text=True)
    if result.stdout.strip():
        print(f"  Custom statuses: {result.stdout.strip()}")
    else:
        print("  ⚠️  No custom statuses configured! Run: dbs init")
    print()

    print("Checking pipeline statuses...")
    for status in ["open", "reviewing", "testing", "merging", "acceptance"]:
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


