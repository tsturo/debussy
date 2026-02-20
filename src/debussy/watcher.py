"""Watcher - spawns agents based on bead status."""

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

os.environ.pop("ANTHROPIC_API_KEY", None)

from .bead_client import get_bead_status
from .config import (
    AGENT_TIMEOUT, POLL_INTERVAL, SESSION_NAME,
    HEARTBEAT_TICKS, STATUS_IN_PROGRESS, STATUS_OPEN,
    atomic_write, get_config, log,
)
from .pipeline_checker import auto_close_parents, check_pipeline, release_ready, reset_orphaned
from .tmux import tmux_windows as get_tmux_windows
from .transitions import (
    MAX_RETRIES,
    ensure_stage_transition, record_event,
)
from .worktree import cleanup_orphaned_branches, cleanup_stale_worktrees, remove_worktree

MIN_AGENT_RUNTIME = 30


@dataclass
class AgentInfo:
    bead: str
    role: str
    name: str
    spawned_stage: str = ""
    claimed: bool = False
    tmux: bool = False
    proc: subprocess.Popen | None = None
    log_path: str = ""
    log_handle: object = field(default=None, repr=False)
    started_at: float = field(default_factory=time.time)
    worktree_path: str = ""

    def is_alive(self, tmux_windows: set[str] | None = None) -> bool:
        if self.tmux:
            if tmux_windows is None:
                tmux_windows = get_tmux_windows()
            return self.name in tmux_windows
        return self.proc is not None and self.proc.poll() is None

    def is_done(self) -> bool:
        current = get_bead_status(self.bead)
        if current is None:
            return False
        if current == STATUS_IN_PROGRESS and not self.claimed:
            self.claimed = True
        return self.claimed and current != STATUS_IN_PROGRESS

    def stop(self):
        if self.tmux:
            subprocess.run(
                ["tmux", "kill-window", "-t", f"{SESSION_NAME}:{self.name}"],
                capture_output=True
            )
        elif self.proc:
            self.proc.terminate()

    def cleanup(self):
        if self.log_handle:
            self.log_handle.close()


class Watcher:
    def __init__(self):
        self.running: dict[str, AgentInfo] = {}
        self.queued: set[str] = set()
        self.used_names: set[str] = set()
        self.failures: dict[str, int] = {}
        self.empty_branch_retries: dict[str, int] = {}
        self.rejections: dict[str, int] = {}
        self.cooldowns: dict[str, float] = {}
        self.blocked_failures: set[str] = set()
        self.should_exit = False
        self.state_file = Path(".debussy/watcher_state.json")
        self._rejections_file = Path(".debussy/rejections.json")
        self._cached_windows: set[str] | None = None
        self._load_rejections()
        cleanup_stale_worktrees()
        cleanup_orphaned_branches()

    def _load_rejections(self):
        try:
            if self._rejections_file.exists():
                self.rejections = json.loads(self._rejections_file.read_text())
        except (OSError, ValueError):
            pass

    def _save_rejections(self):
        try:
            atomic_write(self._rejections_file, json.dumps(self.rejections))
        except OSError:
            pass

    def _refresh_tmux_cache(self):
        has_tmux = any(a.tmux for a in self.running.values())
        self._cached_windows = get_tmux_windows() if has_tmux else None

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
            state[agent.bead] = entry
        atomic_write(self.state_file, json.dumps(state))

    def is_bead_running(self, bead_id: str) -> bool:
        return any(a.bead == bead_id and a.is_alive(self._cached_windows) for a in self.running.values())

    def is_at_capacity(self) -> bool:
        max_total = get_config().get("max_total_agents", 8)
        return len(self._alive_agents()) >= max_total

    def has_running_role(self, role: str) -> bool:
        return any(a.role == role for a in self._alive_agents())

    def _check_timeouts(self):
        now = time.time()
        timeout = get_config().get("agent_timeout", AGENT_TIMEOUT)
        for key, agent in list(self.running.items()):
            if not agent.is_alive(self._cached_windows):
                continue
            elapsed = now - agent.started_at
            if elapsed < timeout:
                continue
            log(f"{agent.name} timed out after {int(elapsed)}s on {agent.bead}", "⏰")
            record_event(agent.bead, "timeout", stage=agent.spawned_stage, agent=agent.name)
            agent.stop()
            try:
                subprocess.run(
                    ["bd", "comment", agent.bead, f"Agent {agent.name} timed out after {int(elapsed)}s"],
                    capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["bd", "update", agent.bead, "--status", STATUS_OPEN],
                    capture_output=True, timeout=5,
                )
            except (subprocess.SubprocessError, OSError):
                pass
            self._remove_agent(key, agent)

    def _remove_agent(self, key: str, agent: AgentInfo):
        agent.cleanup()
        if agent.worktree_path:
            try:
                remove_worktree(agent.name)
            except (subprocess.SubprocessError, OSError) as e:
                log(f"Failed to remove worktree for {agent.name}: {e}", "⚠️")
        if self._cached_windows is not None:
            self._cached_windows.discard(agent.name)
        del self.running[key]

    def cleanup_finished(self):
        cleaned = False
        for key, agent in list(self.running.items()):
            if agent.tmux and agent.is_alive(self._cached_windows):
                if agent.is_done():
                    log(f"{agent.name} completed {agent.bead}", "✅")
                    agent.stop()
                    ensure_stage_transition(self, agent)
                    self.failures.pop(agent.bead, None)
                    self._remove_agent(key, agent)
                    cleaned = True
                continue

            if not agent.is_alive(self._cached_windows):
                elapsed = time.time() - agent.started_at
                bead_status = get_bead_status(agent.bead)
                if agent.tmux:
                    agent_completed = agent.claimed and bead_status not in (STATUS_IN_PROGRESS, None)
                else:
                    agent_completed = elapsed >= MIN_AGENT_RUNTIME and bead_status != STATUS_IN_PROGRESS
                if agent_completed:
                    ensure_stage_transition(self, agent)
                    self.failures.pop(agent.bead, None)
                    log(f"{agent.name} finished {agent.bead}", "🛑")
                else:
                    self.failures[agent.bead] = self.failures.get(agent.bead, 0) + 1
                    log(f"{agent.name} died on {agent.bead} after {int(elapsed)}s, status={bead_status} (attempt {self.failures[agent.bead]}/{MAX_RETRIES})", "💥")
                    if bead_status == STATUS_IN_PROGRESS:
                        try:
                            subprocess.run(
                                ["bd", "update", agent.bead, "--status", STATUS_OPEN],
                                capture_output=True, timeout=5,
                            )
                        except (subprocess.SubprocessError, OSError):
                            pass
                self._remove_agent(key, agent)
                cleaned = True

        if cleaned:
            self.save_state()

    def _log_heartbeat(self):
        active = [(a.name, a.bead) for a in self._alive_agents()]
        if active:
            log(f"Active ({len(active)}):", "🔄")
            for name, bead in active:
                log(f"  {name} → {bead}", "")
        else:
            log("Idle", "💤")

    def _shutdown(self):
        log("Stopping agents...", "🛑")
        for agent in self.running.values():
            agent.stop()
        log("Watcher stopped")

    def signal_handler(self, signum, frame):
        self.should_exit = True

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        log(f"Watcher started (poll every {POLL_INTERVAL}s)", "👀")

        tick = 0
        while not self.should_exit:
            try:
                self._refresh_tmux_cache()
                self._check_timeouts()
                self.cleanup_finished()
                reset_orphaned(self)

                if tick % 3 == 0:
                    auto_close_parents(self)

                if not get_config().get("paused", False):
                    self._refresh_tmux_cache()
                    release_ready(self)
                    check_pipeline(self)

                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._log_heartbeat()
            except Exception as e:
                log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
