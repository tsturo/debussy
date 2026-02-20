"""Tmux session and window management for Debussy."""

import os
import signal
import subprocess
import time
from pathlib import Path

from .config import CLAUDE_STARTUP_DELAY, SESSION_NAME, YOLO_MODE
from .prompts import CONDUCTOR_PROMPT


def run_tmux(*args, check=True):
    return subprocess.run(["tmux", *args], capture_output=True, check=check)


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


def create_tmux_layout():
    run_tmux("kill-session", "-t", SESSION_NAME, check=False)
    run_tmux("new-session", "-d", "-s", SESSION_NAME, "-n", "main")

    t = f"{SESSION_NAME}:main"
    run_tmux("split-window", "-h", "-p", "33", "-t", t)
    run_tmux("split-window", "-h", "-p", "50", "-t", f"{t}.0")
    run_tmux("split-window", "-v", "-p", "50", "-t", f"{t}.0")

    Path(".debussy").mkdir(parents=True, exist_ok=True)

    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    send_keys(f"{t}.0", claude_cmd)
    send_keys(f"{t}.2", "watch -n 5 'debussy board'")
    send_keys(f"{t}.3", "debussy watch")


PANE_STYLES = {
    "conductor": "fg=colour114",
    "cmd": "default",
    "board": "fg=colour208",
    "watcher": "fg=white",
}


def label_panes():
    t = f"{SESSION_NAME}:main"
    for idx, title in enumerate(["conductor", "cmd", "board", "watcher"]):
        run_tmux("select-pane", "-t", f"{t}.{idx}", "-T", title)
        style = PANE_STYLES.get(title, "default")
        if style != "default":
            run_tmux("select-pane", "-t", f"{t}.{idx}", "-P", style)
    run_tmux("set-option", "-t", SESSION_NAME, "pane-border-status", "top")
    run_tmux("set-option", "-t", SESSION_NAME, "pane-border-format", " #{pane_title} ")
    run_tmux("select-window", "-t", f"{SESSION_NAME}:main")
    run_tmux("select-pane", "-t", f"{t}.0")


def send_conductor_prompt(requirement: str | None):
    prompt = CONDUCTOR_PROMPT
    if requirement:
        prompt = f"{prompt}\n\nUser requirement: {requirement}"

    target = f"{SESSION_NAME}:main.0"
    time.sleep(CLAUDE_STARTUP_DELAY)
    send_keys(target, prompt, literal=True)
    time.sleep(0.5)
    subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], check=True)


def stop_watcher():
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{SESSION_NAME}:main.3", "C-c"],
        capture_output=True,
    )


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
