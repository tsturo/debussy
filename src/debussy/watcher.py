"""Watcher - spawns agents based on task status."""

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

os.environ.pop("ANTHROPIC_API_KEY", None)

from .config import (
    AGENT_TIMEOUT, POLL_INTERVAL, SESSION_NAME,
    HEARTBEAT_TICKS, STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    _ensure_gitignored, atomic_write, get_config, log,
)
from .pipeline_checker import check_pipeline, release_ready, reset_orphaned
from .takt import get_db, get_task, init_db, list_tasks, release_task, add_comment
from .takt.log import add_log
from .tmux import send_keys, run_tmux, tmux_window_id_names, tmux_window_ids as get_tmux_windows
from .transitions import MAX_RETRIES, ensure_stage_transition
from .diagnostics import comment_on_task, format_death_comment, read_log_tail
from .worktree import cleanup_orphaned_branches, cleanup_stale_worktrees, remove_worktree

MIN_AGENT_RUNTIME = 30


def _get_task_status(task_id: str) -> str | None:
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

    def is_done(self) -> bool:
        current = _get_task_status(self.task)
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


class Watcher:
    LOCK_FILE = Path(".debussy/watcher.lock")

    def __init__(self):
        self.running: dict[str, AgentInfo] = {}
        self.queued: set[str] = set()
        self.used_names: set[str] = set()
        self.failures: dict[str, int] = {}
        self.empty_branch_retries: dict[str, int] = {}
        self.rejections: dict[str, int] = {}
        self.spawn_counts: dict[str, int] = {}
        self.blocked_failures: set[str] = set()
        self.should_exit = False
        self.state_file = Path(".debussy/watcher_state.json")
        self._rejections_file = Path(".debussy/rejections.json")
        self._empty_branch_file = Path(".debussy/empty_branch_retries.json")
        self._cached_windows: set[str] | None = None
        self.last_notified_tasks: str = ""
        self._load_rejections()
        self._load_empty_branch_retries()
        _ensure_gitignored()
        cleanup_stale_worktrees()
        cleanup_orphaned_branches()
        init_db()

    def _acquire_lock(self) -> bool:
        self.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if self.LOCK_FILE.exists():
            try:
                pid = int(self.LOCK_FILE.read_text().strip())
                if pid != os.getpid():
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGTERM)
                    log(f"Stopping previous watcher (PID {pid})", "🧹")
                    for _ in range(10):
                        time.sleep(0.5)
                        try:
                            os.kill(pid, 0)
                        except OSError:
                            break
                    else:
                        log(f"Previous watcher (PID {pid}) did not stop", "⚠️")
                        return False
            except (ValueError, OSError):
                pass
        self.LOCK_FILE.write_text(str(os.getpid()))
        return True

    def _kill_stale_watchers(self):
        if not self.LOCK_FILE.exists():
            return
        try:
            pid = int(self.LOCK_FILE.read_text().strip())
            if pid == os.getpid():
                return
            os.kill(pid, signal.SIGTERM)
            log(f"Killed stale watcher (PID {pid})", "🧹")
        except (ValueError, OSError):
            pass

    def _release_lock(self):
        try:
            if self.LOCK_FILE.exists():
                pid = int(self.LOCK_FILE.read_text().strip())
                if pid == os.getpid():
                    self.LOCK_FILE.unlink()
        except (ValueError, OSError):
            pass

    def _load_rejections(self):
        try:
            if self._rejections_file.exists():
                self.rejections = json.loads(self._rejections_file.read_text())
        except (OSError, ValueError):
            pass

    def _save_rejections(self):
        try:
            atomic_write(self._rejections_file, json.dumps(self.rejections))
        except OSError as e:
            log(f"Failed to persist rejections: {e}", "⚠️")

    def _load_empty_branch_retries(self):
        try:
            if self._empty_branch_file.exists():
                self.empty_branch_retries = json.loads(self._empty_branch_file.read_text())
        except (OSError, ValueError):
            pass

    def _save_empty_branch_retries(self):
        try:
            atomic_write(self._empty_branch_file, json.dumps(self.empty_branch_retries))
        except OSError:
            pass

    def _refresh_tmux_cache(self):
        use_tmux = get_config().get("use_tmux_windows", False)
        has_tmux = use_tmux or any(a.tmux for a in self.running.values())
        self._cached_windows = get_tmux_windows() if has_tmux else None

    AGENT_ROLES = {"developer", "reviewer", "security-reviewer", "integrator", "tester"}

    def _kill_orphan_windows(self):
        info = tmux_window_id_names()
        if not info:
            return
        known_ids = {a.window_id for a in self.running.values() if a.tmux and a.window_id}
        for wid, name in info.items():
            if wid in known_ids:
                continue
            matched_role = None
            for r in self.AGENT_ROLES:
                if name.startswith(f"{r}-"):
                    matched_role = r
                    break
            if matched_role is None:
                continue
            try:
                subprocess.run(["tmux", "kill-window", "-t", wid], capture_output=True)
                log(f"Killed orphan window: {name}", "🧹")
            except (subprocess.SubprocessError, OSError):
                pass

    def _alive_agents(self) -> list[AgentInfo]:
        return [a for a in self.running.values() if a.is_alive(self._cached_windows)]

    def save_state(self):
        state = {}
        for agent in self._alive_agents():
            entry = {
                "agent": agent.name,
                "role": agent.role,
                "log": agent.log_path,
                "tmux": agent.tmux,
                "worktree_path": agent.worktree_path,
                "started_at": agent.started_at,
            }
            if agent.proc:
                entry["pid"] = agent.proc.pid
            state[agent.task] = entry
        atomic_write(self.state_file, json.dumps(state))

    def is_task_running(self, task_id: str) -> bool:
        return any(a.task == task_id and a.is_alive(self._cached_windows) for a in self.running.values())

    def is_at_capacity(self) -> bool:
        max_total = get_config().get("max_total_agents", 8)
        return len(self._alive_agents()) >= max_total

    def has_running_role(self, role: str) -> bool:
        return any(a.role == role for a in self._alive_agents())

    def count_running_role(self, role: str) -> int:
        return sum(1 for a in self._alive_agents() if a.role == role)

    def _check_timeouts(self):
        now = time.time()
        timeout = get_config().get("agent_timeout", AGENT_TIMEOUT)
        for key, agent in list(self.running.items()):
            if not agent.is_alive(self._cached_windows):
                continue
            elapsed = now - agent.started_at
            if elapsed < timeout:
                continue
            log(f"{agent.name} timed out after {int(elapsed)}s on {agent.task}", "⏰")
            agent.stop()
            with get_db() as db:
                add_comment(db, agent.task, "watcher",
                            f"Agent {agent.name} timed out after {int(elapsed)}s")
                add_log(db, agent.task, "transition", "watcher", "timeout")
                release_task(db, agent.task)
            self._remove_agent(key, agent)

    def _remove_agent(self, key: str, agent: AgentInfo):
        agent.cleanup()
        if agent.worktree_path:
            try:
                remove_worktree(agent.name)
            except (subprocess.SubprocessError, OSError) as e:
                log(f"Failed to remove worktree for {agent.name}: {e}", "⚠️")
        self.used_names.discard(agent.name)
        if self._cached_windows is not None:
            if agent.window_id:
                self._cached_windows.discard(agent.window_id)
            else:
                self._cached_windows.discard(agent.name)
        del self.running[key]

    def cleanup_finished(self):
        cleaned = False
        transitioned = False
        for key, agent in list(self.running.items()):
            if agent.tmux and agent.is_alive(self._cached_windows):
                if agent.is_done():
                    log(f"{agent.name} completed {agent.task}", "✅")
                    agent.stop()
                    if ensure_stage_transition(self, agent):
                        self.failures.pop(agent.task, None)
                        transitioned = True
                    self._remove_agent(key, agent)
                    cleaned = True
                continue

            if not agent.is_alive(self._cached_windows):
                elapsed = time.time() - agent.started_at
                task_status = _get_task_status(agent.task)
                if agent.tmux:
                    agent_completed = agent.claimed and task_status not in (STATUS_ACTIVE, None)
                else:
                    agent_completed = elapsed >= MIN_AGENT_RUNTIME and task_status != STATUS_ACTIVE
                if agent_completed:
                    if ensure_stage_transition(self, agent):
                        self.failures.pop(agent.task, None)
                        transitioned = True
                    log(f"{agent.name} finished {agent.task}", "✔️")
                else:
                    self.failures[agent.task] = self.failures.get(agent.task, 0) + 1
                    log(f"{agent.name} died on {agent.task} after {int(elapsed)}s, status={task_status} (attempt {self.failures[agent.task]}/{MAX_RETRIES})", "💥")
                    log_tail = read_log_tail(agent.log_path) if agent.log_path else ""
                    comment = format_death_comment(agent.name, int(elapsed), str(task_status), log_tail)
                    comment_on_task(agent.task, comment)
                    if task_status == STATUS_ACTIVE:
                        with get_db() as db:
                            release_task(db, agent.task)
                self._remove_agent(key, agent)
                cleaned = True

        if cleaned:
            self.save_state()
            self._save_empty_branch_retries()

    def _notify_conductor(self):
        if not get_config().get("notify_conductor", False):
            return
        try:
            with get_db() as db:
                all_tasks = list_tasks(db)

            messages = []
            needs_attention = set()
            blocked = []
            backlog_no_deps = []

            for task in all_tasks:
                task_id = task.get("id")
                if not task_id:
                    continue
                status = task.get("status")
                stage = task.get("stage")

                if status == STATUS_BLOCKED:
                    blocked.append(task_id)
                    needs_attention.add(f"{task_id}_blocked")
                elif status == STATUS_PENDING and stage == "backlog":
                    if not task.get("dependencies"):
                        backlog_no_deps.append(task_id)
                        needs_attention.add(f"{task_id}_needs_stage")

            if blocked:
                messages.append(f"{', '.join(blocked)} (blocked)")
            if backlog_no_deps:
                messages.append(f"{', '.join(backlog_no_deps)} (needs stage)")

            if not messages:
                self.last_notified_tasks = ""
                return

            notify_state = ",".join(sorted(needs_attention))
            if notify_state == self.last_notified_tasks:
                return

            self.last_notified_tasks = notify_state

            msg = f"Tasks needing attention: {'; '.join(messages)}"
            log(msg, "📢")
            target = f"{SESSION_NAME}:main.0"
            send_keys(target, msg, literal=True)
            run_tmux("send-keys", "-t", target, "Enter")

        except Exception as e:
            log(f"Failed to notify conductor: {e}", "⚠️")

    def _log_heartbeat(self):
        active = [(a.name, a.task) for a in self._alive_agents()]
        if active:
            log(f"Active ({len(active)}):", "🔄")
            for name, task_id in active:
                log(f"  {name} → {task_id}", "")
        else:
            log("Idle", "💤")

    def _shutdown(self):
        log("Stopping agents...", "🛑")
        for agent in self.running.values():
            agent.stop()
        self._release_lock()
        log("Watcher stopped")

    def signal_handler(self, signum, frame):
        self.should_exit = True

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGHUP, self.signal_handler)

        self._kill_stale_watchers()

        if not self._acquire_lock():
            log("Another watcher is already running", "🔒")
            return

        log(f"Watcher started (poll every {POLL_INTERVAL}s)", "👀")
        self._kill_orphan_windows()

        info = tmux_window_id_names()
        remaining = len(info) if info else 0
        log(f"Startup: {remaining} tmux window(s) after orphan cleanup", "📊")

        tick = 0
        while not self.should_exit:
            try:
                self._refresh_tmux_cache()
                self._check_timeouts()
                self.cleanup_finished()
                self._kill_orphan_windows()
                reset_orphaned(self)

                if not get_config().get("paused", False):
                    self._refresh_tmux_cache()
                    release_ready(self)
                    check_pipeline(self)

                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._notify_conductor()
                    self._log_heartbeat()
                    cleanup_orphaned_branches()
            except Exception as e:
                log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
