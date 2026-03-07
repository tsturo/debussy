"""Tmux session and window management for Debussy."""

import os
import signal
import subprocess
from pathlib import Path

import shlex

from .config import SESSION_NAME, YOLO_MODE, get_config
from .prompts import get_conductor_system_prompt, get_conductor_user_message


def run_tmux(*args, check=True):
    result = subprocess.run(["tmux", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        err = result.stderr.strip() or "unknown error"
        raise RuntimeError(f"tmux {' '.join(str(a) for a in args)} failed: {err}")
    return result


def send_keys(target: str, keys: str, literal: bool = False):
    cmd = ["tmux", "send-keys"]
    if literal:
        cmd.append("-l")
    cmd.extend(["-t", target, keys])
    if not literal:
        cmd.append("C-m")
    subprocess.run(cmd, check=True)


def tmux_windows() -> set[str]:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", SESSION_NAME, "-F", "#{window_name}"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    return set(result.stdout.strip().split('\n'))


def tmux_window_ids() -> set[str]:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", SESSION_NAME, "-F", "#{window_id}"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    return set(result.stdout.strip().split('\n'))


def tmux_window_id_names() -> dict[str, str]:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", SESSION_NAME, "-F", "#{window_id}\t#{window_name}"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    info = {}
    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t', 1)
        if len(parts) == 2:
            info[parts[0]] = parts[1]
    return info


def create_tmux_layout(requirement: str | None = None):
    run_tmux("kill-session", "-t", SESSION_NAME, check=False)
    run_tmux("new-session", "-d", "-s", SESSION_NAME, "-n", "main")

    t = f"{SESSION_NAME}:main"
    run_tmux("split-window", "-h", "-t", t)
    run_tmux("split-window", "-h", "-t", f"{t}.0")

    Path(".debussy").mkdir(parents=True, exist_ok=True)

    system_prompt = get_conductor_system_prompt()
    prompt_path = Path(".debussy/conductor-prompt.md")
    prompt_path.write_text(system_prompt)
    user_message = get_conductor_user_message(requirement)
    cfg = get_config()
    conductor_model = cfg.get("role_models", {}).get("conductor")
    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    if conductor_model:
        claude_cmd += f" --model {shlex.quote(conductor_model)}"
    claude_cmd += f" --system-prompt \"$(cat {shlex.quote(str(prompt_path))})\" {shlex.quote(user_message)}"
    send_keys(f"{t}.0", claude_cmd)
    send_keys(f"{t}.1", "watch -n 5 'debussy board'")
    send_keys(f"{t}.2", "debussy watch 2>&1 | tee .debussy/logs/watcher.log")


def label_panes():
    t = f"{SESSION_NAME}:main"
    for idx, title in enumerate(["conductor", "board", "watcher"]):
        run_tmux("select-pane", "-t", f"{t}.{idx}", "-T", title)
    run_tmux("set-option", "-t", SESSION_NAME, "pane-border-status", "top")
    run_tmux("set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} ")
    run_tmux("select-window", "-t", f"{SESSION_NAME}:main")
    run_tmux("select-pane", "-t", f"{t}.0")



def stop_watcher():
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{SESSION_NAME}:main.3", "C-c"],
        capture_output=True,
    )


def list_debussy_sessions() -> list[dict]:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    sessions = []
    for name in result.stdout.strip().split('\n'):
        if not name.startswith("debussy-"):
            continue
        path_result = subprocess.run(
            ["tmux", "display-message", "-t", f"{name}:main.0", "-p", "#{pane_current_path}"],
            capture_output=True, text=True,
        )
        path = path_result.stdout.strip() if path_result.returncode == 0 else "unknown"
        sessions.append({"session": name, "path": path})
    return sessions


def kill_agent(agent: dict, agent_name: str):
    if agent.get("tmux"):
        subprocess.run(
            ["tmux", "kill-window", "-t", f"{SESSION_NAME}:{agent_name}"],
            capture_output=True,
        )
    elif agent.get("pid"):
        try:
            os.kill(agent["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
