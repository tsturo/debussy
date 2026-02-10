"""Watcher - spawns agents based on bead status."""

import json
import os
import random
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

os.environ.pop("ANTHROPIC_API_KEY", None)

from .config import (
    AGENT_TIMEOUT, POLL_INTERVAL, YOLO_MODE, SESSION_NAME,
    HEARTBEAT_TICKS, STATUS_TO_ROLE, atomic_write,
    get_config, log,
)
from .prompts import get_prompt

COMPOSERS = [
    "bach", "mozart", "beethoven", "chopin", "liszt", "brahms", "wagner",
    "tchaikovsky", "dvorak", "grieg", "rachmaninoff", "ravel", "prokofiev",
    "stravinsky", "gershwin", "copland", "bernstein", "glass", "reich",
    "handel", "haydn", "schubert", "schumann", "mendelssohn", "verdi", "puccini",
    "rossini", "vivaldi", "mahler", "bruckner", "sibelius", "elgar", "holst",
    "debussy", "faure", "satie", "bizet", "offenbach", "berlioz", "saint-saens",
    "mussorgsky", "rimsky", "borodin", "scriabin", "shostakovich", "khachaturian",
    "bartok", "kodaly", "janacek", "smetana", "nielsen", "vaughan", "britten",
    "walton", "tippett", "barber", "ives", "cage", "feldman", "adams", "corigliano",
    "pärt", "gorecki", "ligeti", "xenakis", "boulez", "stockhausen", "berio",
    "nono", "messiaen", "dutilleux", "penderecki", "lutoslawski", "takemitsu",
]


def _tmux_windows() -> set[str]:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", SESSION_NAME, "-F", "#{window_name}"],
        capture_output=True, text=True
    )
    return set(result.stdout.strip().split('\n'))


@dataclass
class AgentInfo:
    bead: str
    role: str
    name: str
    tmux: bool = False
    proc: subprocess.Popen | None = None
    log_path: str = ""
    log_handle: object = field(default=None, repr=False)
    started_at: float = field(default_factory=time.time)

    def is_alive(self, tmux_windows: set[str] | None = None) -> bool:
        if self.tmux:
            if tmux_windows is None:
                tmux_windows = _tmux_windows()
            return self.name in tmux_windows
        return self.proc is not None and self.proc.poll() is None

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
        self.should_exit = False
        self.state_file = Path(".debussy/watcher_state.json")
        self._cached_windows: set[str] | None = None

    def _refresh_tmux_cache(self):
        has_tmux = any(a.tmux for a in self.running.values())
        self._cached_windows = _tmux_windows() if has_tmux else None

    def _alive_agents(self) -> list[AgentInfo]:
        return [a for a in self.running.values() if a.is_alive(self._cached_windows)]

    def save_state(self):
        state = {}
        for agent in self._alive_agents():
            state[agent.bead] = {
                "agent": agent.name,
                "role": agent.role,
                "log": agent.log_path,
                "tmux": agent.tmux,
            }
        atomic_write(self.state_file, json.dumps(state))

    def get_agent_name(self, role: str) -> str:
        available = [n for n in COMPOSERS if f"{role}-{n}" not in self.used_names]
        if available:
            name = random.choice(available)
            full_name = f"{role}-{name}"
            self.used_names.add(full_name)
            return full_name
        return f"{role}-{len(self.used_names)}"

    def is_bead_running(self, bead_id: str) -> bool:
        return any(a.bead == bead_id and a.is_alive(self._cached_windows) for a in self.running.values())

    def is_at_capacity(self) -> bool:
        max_total = get_config().get("max_total_agents", 6)
        return len(self._alive_agents()) >= max_total

    def is_blocked(self, bead_id: str) -> bool:
        try:
            result = subprocess.run(
                ["bd", "show", bead_id],
                capture_output=True, text=True, timeout=5
            )
            return "Blocked by" in result.stdout
        except Exception:
            return False

    def extract_bead_id(self, line: str) -> str | None:
        parts = line.split()
        if len(parts) < 2:
            return None
        candidate = parts[1]
        if candidate.startswith("["):
            return parts[0] if not parts[0].startswith(("○", "●", "◐", "✓", "✗")) else None
        return candidate

    def is_epic_or_feature(self, line: str) -> bool:
        lower = line.lower()
        return "[epic]" in lower or "[feature]" in lower

    def spawn_agent(self, role: str, bead_id: str, status: str):
        key = f"{role}:{bead_id}"

        if key in self.running and self.running[key].is_alive(self._cached_windows):
            return

        agent_name = self.get_agent_name(role)
        log(f"Spawning {agent_name} for {bead_id}", "🚀")

        prompt = get_prompt(role, bead_id, status)

        cfg = get_config()
        use_tmux = cfg.get("use_tmux_windows", False) and os.environ.get("TMUX") is not None

        if use_tmux:
            self._spawn_tmux(key, agent_name, bead_id, role, prompt)
        else:
            self._spawn_background(key, agent_name, bead_id, role, prompt)

    def _spawn_tmux(self, key: str, agent_name: str, bead_id: str, role: str, prompt: str):
        claude_cmd = "claude"
        if YOLO_MODE:
            claude_cmd += " --dangerously-skip-permissions"

        escaped_prompt = prompt.replace("'", "'\"'\"'")
        log_file = Path(".debussy/agent_output.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        shell_cmd = (
            f"export DEBUSSY_ROLE={role} DEBUSSY_BEAD={bead_id}; "
            f"echo '\\n=== {agent_name} ({bead_id}) ===' >> {log_file}; "
            f"script -q /dev/null {claude_cmd} --print '{escaped_prompt}' | tee -a {log_file}"
        )

        try:
            subprocess.run([
                "tmux", "new-window", "-d", "-t", SESSION_NAME,
                "-n", agent_name, "bash", "-c", shell_cmd
            ], check=True)
            self.running[key] = AgentInfo(
                bead=bead_id, role=role, name=agent_name, tmux=True,
            )
            if self._cached_windows is not None:
                self._cached_windows.add(agent_name)
            self.save_state()
        except Exception as e:
            log(f"Failed to spawn tmux window: {e}", "✗")

    def _spawn_background(self, key: str, agent_name: str, bead_id: str, role: str, prompt: str):
        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        logs_dir = Path(".debussy/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"{agent_name}.log"

        try:
            env = os.environ.copy()
            env["DEBUSSY_ROLE"] = role
            env["DEBUSSY_BEAD"] = bead_id
            log_handle = open(log_file, "wb", buffering=0)
            proc = subprocess.Popen(
                cmd, cwd=os.getcwd(), env=env,
                stdout=log_handle, stderr=subprocess.STDOUT,
                bufsize=0
            )
            self.running[key] = AgentInfo(
                bead=bead_id, role=role, name=agent_name,
                proc=proc, log_path=str(log_file), log_handle=log_handle,
            )
            self.save_state()
        except Exception as e:
            log(f"Failed to spawn {role}: {e}", "✗")

    def check_pipeline(self):
        for status, role in STATUS_TO_ROLE.items():
            try:
                result = subprocess.run(
                    ["bd", "list", "--status", status],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0 or not result.stdout.strip():
                    continue

                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue

                    bead_id = self.extract_bead_id(line)
                    if not bead_id:
                        continue

                    if self.is_epic_or_feature(line):
                        continue

                    if self.is_bead_running(bead_id):
                        continue

                    if self.is_blocked(bead_id):
                        continue

                    if self.is_at_capacity():
                        if bead_id not in self.queued:
                            log(f"Queued: {bead_id} waiting for agent slot", "⏳")
                            self.queued.add(bead_id)
                        continue

                    self.queued.discard(bead_id)
                    self.spawn_agent(role, bead_id, status)

            except subprocess.TimeoutExpired:
                log(f"Timeout checking {status}", "⚠️")
            except Exception as e:
                log(f"Error checking {status}: {e}", "⚠️")

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
            agent.stop()
            try:
                subprocess.run(
                    ["bd", "comment", agent.bead, f"Agent {agent.name} timed out after {int(elapsed)}s"],
                    capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["bd", "update", agent.bead, "--status", "planning"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

    def cleanup_finished(self):
        cleaned = False
        for key, agent in list(self.running.items()):
            if not agent.is_alive(self._cached_windows):
                agent.cleanup()
                log(f"{agent.name} finished {agent.bead}", "🛑")
                self.used_names.discard(agent.name)
                del self.running[key]
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
                self.check_pipeline()
                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._log_heartbeat()
            except Exception as e:
                log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
