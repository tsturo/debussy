"""CLI commands for Debussy."""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .bead_client import get_bead_status
from .config import (
    SESSION_NAME, STATUS_IN_PROGRESS, STATUS_OPEN,
    clean_config, get_config, log, parse_value, set_config,
)
from .tmux import (
    create_tmux_layout, kill_agent, label_panes, send_conductor_prompt,
)
from .worktree import remove_worktree, remove_all_worktrees


def _preflight_check() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log("Not a git repository", "\u2717")
        return False
    result = subprocess.run(
        ["git", "remote"], capture_output=True, text=True,
    )
    if "origin" not in result.stdout.split():
        log("No 'origin' remote configured. Debussy requires a git remote.", "\u2717")
        log("Add one with: git remote add origin <url>", "")
        return False
    return True


def cmd_start(args):
    if not _preflight_check():
        return 1
    clean_config()
    if getattr(args, "paused", False):
        set_config("paused", True)
    else:
        set_config("paused", False)
    create_tmux_layout()
    send_conductor_prompt(getattr(args, "requirement", None))
    label_panes()

    print("\U0001f3bc Debussy started")
    print("")
    print("Layout:")
    print("  \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510")
    print("  \u2502conductor \u2502          \u2502         \u2502")
    print("  \u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524  board   \u2502 watcher \u2502")
    print("  \u2502   cmd    \u2502          \u2502         \u2502")
    print("  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    if not _preflight_check():
        return 1
    from .watcher import Watcher
    Watcher().run()


def _upgrade_bd():
    old = subprocess.run(["bd", "version"], capture_output=True, text=True)
    old_ver = old.stdout.strip() if old.returncode == 0 else "unknown"
    log(f"Current bd: {old_ver}", "\U0001f4e6")
    log("Upgrading bd...", "\u2b06\ufe0f")
    result = subprocess.run([
        "go", "install", "github.com/steveyegge/beads/cmd/bd@latest"
    ])
    if result.returncode == 0:
        new = subprocess.run(["bd", "version"], capture_output=True, text=True)
        log(f"Upgraded bd to: {new.stdout.strip()}", "\u2713")
    else:
        log("bd upgrade failed", "\u2717")
    return result.returncode


def cmd_upgrade(args):
    from . import __version__
    log(f"Current version: {__version__}", "\U0001f4e6")
    log("Upgrading debussy...", "\u2b06\ufe0f")
    result = subprocess.run([
        "pipx", "install", "--force",
        "git+https://github.com/tsturo/debussy.git"
    ])
    if result.returncode == 0:
        new_ver = subprocess.run(
            ["debussy", "--version"],
            capture_output=True, text=True
        )
        log(f"Upgraded to: {new_ver.stdout.strip()}", "\u2713")
    else:
        log("Upgrade failed", "\u2717")
    return result.returncode


def cmd_restart(args):
    if args.upgrade:
        result = cmd_upgrade(args)
        if result != 0:
            return result

    cmd_pause(args)
    set_config("paused", False)

    cwd = os.getcwd()
    subprocess.Popen(
        ["bash", "-c",
         f"sleep 1 && tmux kill-session -t {SESSION_NAME} 2>/dev/null && sleep 1 && cd {cwd} && debussy start"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    log("Restarting in background...", "\U0001f504")


def cmd_config(args):
    if args.key and args.value is not None:
        value = parse_value(args.value)
        set_config(args.key, value)
        log(f"Set {args.key} = {value}", "\u2713")
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
        log(f"Backed up to {backup_path}", "\u2713")
    else:
        log("No .beads directory to backup", "\u26a0\ufe0f")


def cmd_clear(args):
    beads_dir = Path(".beads")
    debussy_dir = Path(".debussy")

    if beads_dir.exists() and not getattr(args, 'force', False):
        result = subprocess.run(["bd", "list"], capture_output=True, text=True)
        task_count = len([l for l in result.stdout.strip().split('\n') if l.strip()]) if result.stdout.strip() else 0
        if task_count > 0:
            print(f"\u26a0\ufe0f  This will delete {task_count} tasks!")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                log("Aborted", "\u2717")
                return 1

    if beads_dir.exists():
        backup_path = _backup_beads()
        if backup_path:
            log(f"Backed up to {backup_path}", "\U0001f4be")
        shutil.rmtree(beads_dir)
        log("Removed .beads", "\U0001f5d1")

    try:
        remove_all_worktrees()
        log("Removed all worktrees", "\U0001f9f9")
    except (subprocess.SubprocessError, OSError):
        pass

    if debussy_dir.exists():
        for item in debussy_dir.iterdir():
            if item.name != "backups":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        log("Cleared .debussy (kept backups)", "\U0001f5d1")

    result = subprocess.run(["bd", "init"], capture_output=True)
    if result.returncode != 0:
        log("Failed to init beads", "\u2717")
        return 1
    log("Initialized fresh beads", "\u2713")


def _reset_bead_to_open(bead_id: str):
    status = get_bead_status(bead_id)
    if status and status == STATUS_IN_PROGRESS:
        subprocess.run(
            ["bd", "comment", bead_id, "Paused by debussy pause"],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            ["bd", "update", bead_id, "--status", STATUS_OPEN],
            capture_output=True, timeout=5,
        )
        log(f"Reset {bead_id} ({status} \u2192 open)", "\u23f8")


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
                log(f"Deleted branch {branch}", "\U0001f5d1")
    except (subprocess.SubprocessError, OSError) as e:
        log(f"Failed to clean branches: {e}", "\u26a0\ufe0f")


def cmd_pause(args):
    set_config("paused", True)

    state_file = Path(".debussy/watcher_state.json")
    state = {}
    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
        except (OSError, ValueError):
            pass

    for bead_id, agent in state.items():
        agent_name = agent.get("agent", "")
        kill_agent(agent, agent_name)
        log(f"Killed {agent_name}", "\U0001f6d1")
        if agent.get("worktree_path"):
            try:
                remove_worktree(agent_name)
            except (subprocess.SubprocessError, OSError):
                pass
        _reset_bead_to_open(bead_id)

    if state_file.exists():
        state_file.unlink()

    log("Pipeline paused", "\u23f8")


def cmd_resume(args):
    set_config("paused", False)
    log("Pipeline resumed", "\u25b6")
