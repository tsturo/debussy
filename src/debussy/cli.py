"""CLI commands for Debussy."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from .config import (
    SESSION_NAME, STATUS_ACTIVE, STATUS_PENDING,
    backup_takt, clean_config, get_config, log, parse_value, set_config,
)
from .takt import get_db, get_task, init_db, release_task, add_comment
from .hooks import install_hooks
from .tmux import (
    create_tmux_layout, kill_agent, label_panes, list_debussy_sessions,
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
    if os.geteuid() == 0:
        raise SystemExit("Debussy cannot run as root. Create a non-root user instead.")
    if not _preflight_check():
        return 1
    clean_config()
    if getattr(args, "paused", False):
        set_config("paused", True)
    else:
        set_config("paused", False)
    install_hooks()
    requirement = getattr(args, "requirement", None)
    create_tmux_layout(requirement)
    label_panes()

    print("\U0001f3bc Debussy started")
    print("")
    print("Layout:")
    print("  \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510")
    print("  \u2502            \u2502          \u2502         \u2502")
    print("  \u2502 conductor  \u2502  board   \u2502 watcher \u2502")
    print("  \u2502            \u2502          \u2502         \u2502")
    print("  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")
    print("")

    subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])


def cmd_watch(args):
    if not _preflight_check():
        return 1
    from .watcher import Watcher
    Watcher().run()


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
            ["pipx", "runpip", "debussy", "show", "debussy"],
            capture_output=True, text=True
        )
        ver = ""
        for line in new_ver.stdout.splitlines():
            if line.startswith("Version:"):
                ver = line.split(":", 1)[1].strip()
                break
        log(f"Upgraded to: {ver}", "\u2713")
    else:
        log("Upgrade failed", "\u2717")
    return result.returncode



def cmd_config(args):
    from .config import KNOWN_KEYS
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
        for k in sorted(KNOWN_KEYS):
            val = cfg.get(k)
            if val is not None:
                print(f"  {k} = {val}")
            else:
                print(f"  {k} -")


def cmd_backup(args):
    backup_path = backup_takt()
    if backup_path:
        log(f"Backed up to {backup_path}", "\u2713")
    else:
        log("No .takt directory to backup", "\u26a0\ufe0f")


def cmd_clear(args):
    takt_dir = Path(".takt")
    debussy_dir = Path(".debussy")

    if takt_dir.exists() and not getattr(args, 'force', False):
        with get_db() as db:
            from .takt import list_tasks
            tasks = list_tasks(db)
        task_count = len(tasks)
        if task_count > 0:
            print(f"\u26a0\ufe0f  This will delete {task_count} tasks!")
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                log("Aborted", "\u2717")
                return 1

    if takt_dir.exists():
        backup_path = backup_takt()
        if backup_path:
            log(f"Backed up to {backup_path}", "\U0001f4be")
        shutil.rmtree(takt_dir)
        log("Removed .takt", "\U0001f5d1")

    try:
        remove_all_worktrees()
        log("Removed all worktrees", "\U0001f9f9")
    except (subprocess.SubprocessError, OSError):
        pass

    PRESERVE = {"backups", "config.json", "conductor-history.md"}
    if debussy_dir.exists():
        for item in debussy_dir.iterdir():
            if item.name in PRESERVE:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        log("Cleared .debussy (kept config, history, backups)", "\U0001f5d1")

    init_db()
    log("Initialized fresh takt database", "\u2713")


def _reset_task_to_pending(task_id: str):
    with get_db() as db:
        task = get_task(db, task_id)
        if task and task["status"] == STATUS_ACTIVE:
            add_comment(db, task_id, "system", "Paused by debussy pause")
            release_task(db, task_id)
            log(f"Reset {task_id} (active \u2192 pending)", "\u23f8")


def _delete_orphan_branches(paused_tasks: set[str]):
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "feature/takt-*"],
            capture_output=True, text=True,
        )
        for line in result.stdout.strip().split('\n'):
            branch = line.strip().lstrip("* ")
            if not branch:
                continue
            task_id = branch.replace("feature/", "")
            if task_id in paused_tasks:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    capture_output=True,
                )
                log(f"Deleted branch {branch}", "\U0001f5d1")
    except (subprocess.SubprocessError, OSError) as e:
        log(f"Failed to clean branches: {e}", "\u26a0\ufe0f")


def _load_watcher_state() -> dict:
    state_file = Path(".debussy/watcher_state.json")
    if state_file.exists():
        try:
            with open(state_file) as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def _save_watcher_state(state: dict):
    state_file = Path(".debussy/watcher_state.json")
    if state:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(state, f)
    elif state_file.exists():
        state_file.unlink()


def _kill_one_agent(task_id: str, agent: dict):
    agent_name = agent.get("agent", "")
    kill_agent(agent, agent_name)
    log(f"Killed {agent_name}", "\U0001f6d1")
    if agent.get("worktree_path"):
        try:
            remove_worktree(agent_name)
        except (subprocess.SubprocessError, OSError):
            pass
    _reset_task_to_pending(task_id)


def _kill_all_agents():
    state = _load_watcher_state()

    for task_id, agent in state.items():
        _kill_one_agent(task_id, agent)

    _save_watcher_state({})


def cmd_pause(args):
    set_config("paused", True)
    _kill_all_agents()
    log("Pipeline paused", "\u23f8")




def cmd_kill_agent(args):
    name = args.name
    state = _load_watcher_state()
    if not state:
        print("No running agents")
        return 1

    for task_id, agent in state.items():
        if agent.get("agent") == name or task_id == name:
            _kill_one_agent(task_id, agent)
            del state[task_id]
            _save_watcher_state(state)
            return 0

    print(f"Agent '{name}' not found. Running agents:")
    for task_id, agent in state.items():
        print(f"  {agent.get('agent', '?')}  ({task_id})")
    return 1


def cmd_resume(args):
    set_config("paused", False)
    log("Pipeline resumed", "\u25b6")


def cmd_sessions(args):
    sessions = list_debussy_sessions()
    if not sessions:
        print("No active sessions")
        return 0
    for s in sessions:
        print(f"  {s['session']}    {s['path']}")


def _find_session(sessions: list[dict], name: str) -> dict | None:
    target = f"debussy-{name}" if not name.startswith("debussy-") else name
    for s in sessions:
        if s["session"] == target:
            return s
    return None


def cmd_kill(args):
    all_sessions = getattr(args, "all", False)
    sessions = list_debussy_sessions()
    if not sessions:
        print("No active sessions")
        return 0

    if all_sessions:
        for s in sessions:
            subprocess.run(["tmux", "kill-session", "-t", s["session"]], capture_output=True)
            log(f"Killed {s['session']}", "\U0001f6d1")
        return 0

    cwd = os.getcwd()
    cwd_name = Path(cwd).name
    target = f"debussy-{cwd_name}"
    session = _find_session(sessions, target)
    if not session:
        print(f"No session for current directory. Active sessions:")
        for s in sessions:
            print(f"  {s['session']}    {s['path']}")
        return 1

    subprocess.run(["tmux", "kill-session", "-t", session["session"]], capture_output=True)
    log(f"Killed {session['session']}", "\U0001f6d1")
    return 0


def cmd_connect(args):
    sessions = list_debussy_sessions()
    if not sessions:
        print("No active sessions")
        return 1

    name = getattr(args, "name", None)

    if not name:
        if len(sessions) == 1:
            session = sessions[0]
        else:
            print("Multiple sessions running. Specify a name:")
            for s in sessions:
                print(f"  {s['session']}    {s['path']}")
            return 1
    else:
        session = _find_session(sessions, name)
        if not session:
            print(f"Session '{name}' not found. Active sessions:")
            for s in sessions:
                print(f"  {s['session']}    {s['path']}")
            return 1

    os.chdir(session["path"])
    os.execvp("tmux", ["tmux", "attach-session", "-t", session["session"]])


