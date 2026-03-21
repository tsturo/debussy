"""Shared types and utilities for the Debussy agent pipeline."""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import SESSION_NAME, STATUS_ACTIVE
from .takt import get_db, get_task
from .tmux import tmux_window_ids as get_tmux_windows


def repo_root() -> Path:
    """Return the git repository root as an absolute path."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("Not inside a git repository")
    return Path(result.stdout.strip())


def get_task_status(task_id: str) -> str | None:
    """Read current task status from takt."""
    with get_db() as db:
        task = get_task(db, task_id)
    return task["status"] if task else None


@dataclass
class AgentInfo:
    task: str
    role: str
    name: str
    spawned_stage: str = ""
    claimed: bool = False
    tmux: bool = False
    window_id: str = ""
    proc: subprocess.Popen | None = None
    log_path: str = ""
    log_handle: object = field(default=None, repr=False)
    started_at: float = field(default_factory=time.time)
    worktree_path: str = ""

    def is_alive(self, tmux_windows: set[str] | None = None) -> bool:
        if self.tmux:
            if tmux_windows is None:
                tmux_windows = get_tmux_windows()
            if self.window_id:
                return self.window_id in tmux_windows
            return self.name in tmux_windows
        return self.proc is not None and self.proc.poll() is None

    def check_completion(self) -> bool:
        """Check if the agent's task has moved past active status.

        Mutates self.claimed as a side effect: once we observe STATUS_ACTIVE,
        we record that the agent did claim the task.  This lets us distinguish
        "agent died before claiming" from "agent finished work" when the
        process/window disappears.
        """
        current = get_task_status(self.task)
        if current is None:
            return False
        if current == STATUS_ACTIVE and not self.claimed:
            self.claimed = True
        return self.claimed and current != STATUS_ACTIVE

    def stop(self):
        if self.tmux:
            target = self.window_id if self.window_id else f"{SESSION_NAME}:{self.name}"
            subprocess.run(
                ["tmux", "kill-window", "-t", target],
                capture_output=True
            )
        elif self.proc:
            self.proc.terminate()

    def cleanup(self):
        if self.log_handle:
            self.log_handle.close()
