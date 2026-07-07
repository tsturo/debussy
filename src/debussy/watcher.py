"""Watcher - spawns agents based on task status."""

import json
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path

from .agent import AgentInfo, get_task_status, repo_root
from .config import (
    AGENT_TIMEOUT, POLL_INTERVAL, SESSION_NAME,
    HEARTBEAT_TICKS, STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    _ensure_gitignored, atomic_write, get_config, log, set_config,
)
from .quota import check_quota, detect_limit_signal, QUOTA_DEFAULT_COOLDOWN
from .pipeline_checker import check_pipeline, release_ready, reset_orphaned
from .takt import get_db, get_task, init_db, list_tasks, release_task, add_comment
from .takt.log import add_log
from .tmux import send_keys, run_tmux, tmux_window_id_names, tmux_window_ids as get_tmux_windows
from .transitions import MAX_RETRIES, ensure_stage_transition
from .diagnostics import comment_on_task, format_death_comment, read_log_tail
from .worktree import cleanup_orphaned_branches, cleanup_stale_worktrees, delete_task_branch, remove_worktree

MIN_AGENT_RUNTIME = 30


class Watcher:

    def __init__(self):
        self._root = repo_root()
        self.running: dict[str, AgentInfo] = {}
        self.queued: set[str] = set()
        self.used_names: set[str] = set()
        self.failures: dict[str, int] = {}
        self.empty_branch_retries: dict[str, int] = {}
        self.spawn_counts: dict[str, int] = {}
        self.blocked_failures: set[str] = set()
        self.preflight_warned: set[str] = set()
        self._last_quota_check = 0.0
        self._quota_warned = 0.0
        self.should_exit = False
        self.lock_file = self._root / ".debussy" / "watcher.lock"
        self.state_file = self._root / ".debussy" / "watcher_state.json"
        self._empty_branch_file = self._root / ".debussy" / "empty_branch_retries.json"
        self._cached_windows: set[str] | None = None
        self.last_notified_tasks: str = ""
        self._load_empty_branch_retries()
        _ensure_gitignored()
        cleanup_stale_worktrees()
        cleanup_orphaned_branches()
        init_db()

    def _acquire_lock(self) -> bool:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text().strip())
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
                # Old process confirmed dead — remove its lock so O_EXCL can succeed
                self.lock_file.unlink(missing_ok=True)
            except (ValueError, OSError):
                # Corrupt lock file or process already gone — remove stale lock
                self.lock_file.unlink(missing_ok=True)
        # Atomic lock creation: O_CREAT|O_EXCL ensures only one watcher wins
        try:
            fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            return False
        return True

    def _kill_stale_watchers(self):
        if not self.lock_file.exists():
            return
        try:
            pid = int(self.lock_file.read_text().strip())
            if pid == os.getpid():
                return
            os.kill(pid, signal.SIGTERM)
            log(f"Killed stale watcher (PID {pid})", "🧹")
        except (ValueError, OSError):
            pass

    def _release_lock(self):
        try:
            if self.lock_file.exists():
                pid = int(self.lock_file.read_text().strip())
                if pid == os.getpid():
                    self.lock_file.unlink()
        except (ValueError, OSError):
            pass

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
        quota_hit = False
        quota_ts = None
        for key, agent in list(self.running.items()):
            if agent.tmux and agent.is_alive(self._cached_windows):
                if agent.check_completion():
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
                task_status = get_task_status(agent.task)
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
                    hit, ts = detect_limit_signal(log_tail)
                    if hit:
                        quota_hit = True
                        if ts is not None:
                            quota_ts = ts if quota_ts is None else min(quota_ts, ts)
                        self.failures[agent.task] = max(0, self.failures.get(agent.task, 0) - 1)
                    comment = format_death_comment(agent.name, int(elapsed), str(task_status), log_tail)
                    comment_on_task(agent.task, comment)
                    if task_status == STATUS_ACTIVE:
                        with get_db() as db:
                            release_task(db, agent.task)
                    # Clean up stale task branch so next developer spawn gets a fresh checkout
                    if agent.role == "developer":
                        try:
                            delete_task_branch(agent.task)
                            log(f"Deleted stale branch feature/{agent.task} after agent death", "🧹")
                        except (subprocess.SubprocessError, OSError) as e:
                            log(f"Failed to delete branch for {agent.task}: {e}", "⚠️")
                self._remove_agent(key, agent)
                cleaned = True

        if cleaned:
            self.save_state()
            self._save_empty_branch_retries()
        return quota_hit, quota_ts

    def _clear_quota_pause(self):
        set_config("paused", False)
        set_config("pause_reason", None)
        set_config("paused_until", None)

    def _warn_quota_unavailable(self, now: float):
        from .quota import QUOTA_CHECK_INTERVAL
        if now - self._quota_warned >= QUOTA_CHECK_INTERVAL:
            self._quota_warned = now
            log("Quota check unavailable (ccusage) — proceeding", "⚠️")

    def _pause_running_agents(self, comment: str):
        for key, agent in list(self.running.items()):
            agent.stop()
            if get_task_status(agent.task) == STATUS_ACTIVE:
                with get_db() as db:
                    add_comment(db, agent.task, "watcher", comment)
                    release_task(db, agent.task)
            self._remove_agent(key, agent)
            if agent.role == "developer":
                try:
                    delete_task_branch(agent.task)
                except (subprocess.SubprocessError, OSError):
                    pass
        self.save_state()

    def _enter_quota_pause(self, reset_at, source: str, status=None):
        cfg = get_config()
        if reset_at is None:
            probe = status or check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
            reset_at = probe.reset_at if probe else None
        if reset_at is None:
            reset_at = time.time() + QUOTA_DEFAULT_COOLDOWN
        detail = f"used {status.used}/{status.limit}" if status else source
        log(f"Quota pause ({source}, {detail}); resuming at {int(reset_at)}", "🪫")
        self._pause_running_agents("Paused: quota limit reached")
        set_config("paused", True)
        set_config("pause_reason", "quota")
        set_config("paused_until", reset_at)

    def _maybe_auto_resume(self):
        cfg = get_config()
        if not cfg.get("paused") or cfg.get("pause_reason") != "quota":
            return
        if not cfg.get("quota_check"):
            self._clear_quota_pause()
            return
        until = cfg.get("paused_until")
        if until is None or time.time() < until:
            return
        status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
        if status is None:
            self._clear_quota_pause()
            return
        if status.exhausted:
            set_config("paused_until", status.reset_at or time.time() + QUOTA_DEFAULT_COOLDOWN)
        else:
            self._last_quota_check = time.time()
            self._clear_quota_pause()

    def _quota_gate(self):
        from .quota import QUOTA_CHECK_INTERVAL
        cfg = get_config()
        if not cfg.get("quota_check"):
            return None
        now = time.time()
        if now - self._last_quota_check < QUOTA_CHECK_INTERVAL:
            return None
        self._last_quota_check = now
        status = check_quota(cfg.get("quota_command"), cfg.get("quota_margin"))
        if status is None:
            self._warn_quota_unavailable(now)
            return None
        return status if status.exhausted else None

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
        for agent in list(self.running.values()):
            agent.stop()
            if agent.worktree_path:
                try:
                    remove_worktree(agent.name)
                except (subprocess.SubprocessError, OSError) as e:
                    log(f"Failed to remove worktree for {agent.name}: {e}", "⚠️")
        self._release_lock()
        log("Watcher stopped")

    def signal_handler(self, signum, frame):
        self.should_exit = True

    def run(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

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
                quota_hit, quota_ts = self.cleanup_finished()
                self._kill_orphan_windows()
                reset_orphaned(self)

                if quota_hit:
                    self._enter_quota_pause(quota_ts, "wall-hit")

                self._maybe_auto_resume()
                if not get_config().get("paused", False):
                    self._refresh_tmux_cache()
                    status = self._quota_gate()
                    if status is not None:
                        self._enter_quota_pause(status.reset_at, "quota", status)
                    else:
                        release_ready(self)
                        check_pipeline(self)

                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._notify_conductor()
                    self._log_heartbeat()
                    cleanup_orphaned_branches()
            except Exception:
                log(f"Error in watcher loop:\n{traceback.format_exc()}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
