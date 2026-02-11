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
    AGENT_TIMEOUT, CLAUDE_STARTUP_DELAY, POLL_INTERVAL, YOLO_MODE, SESSION_NAME,
    HEARTBEAT_TICKS, NEXT_STAGE, STAGE_ORDER, STAGE_TO_ROLE, atomic_write,
    get_config, log,
)
from .prompts import get_prompt

MIN_AGENT_RUNTIME = 30
MAX_RETRIES = 3

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


def _get_bead_json(bead_id: str) -> dict | None:
    try:
        result = subprocess.run(
            ["bd", "show", bead_id, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        pass
    return None


def _get_bead_status(bead_id: str) -> str | None:
    bead = _get_bead_json(bead_id)
    return bead.get("status") if bead else None


def _has_unresolved_deps(bead: dict) -> bool:
    for dep in bead.get("dependencies", []):
        dep_id = dep.get("depends_on_id")
        if not dep_id:
            continue
        dep_status = _get_bead_status(dep_id)
        if dep_status != "closed":
            return True
    return False


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

    def is_alive(self, tmux_windows: set[str] | None = None) -> bool:
        if self.tmux:
            if tmux_windows is None:
                tmux_windows = _tmux_windows()
            return self.name in tmux_windows
        return self.proc is not None and self.proc.poll() is None

    def is_done(self) -> bool:
        current = _get_bead_status(self.bead)
        if current is None:
            return False
        if current == "in_progress" and not self.claimed:
            self.claimed = True
        return self.claimed and current != "in_progress"

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

    def has_running_role(self, role: str) -> bool:
        return any(a.role == role for a in self._alive_agents())

    def spawn_agent(self, role: str, bead_id: str, stage: str):
        key = f"{role}:{bead_id}"

        if key in self.running and self.running[key].is_alive(self._cached_windows):
            return

        agent_name = self.get_agent_name(role)
        log(f"Spawning {agent_name} for {bead_id}", "🚀")

        prompt = get_prompt(role, bead_id, stage)

        cfg = get_config()
        use_tmux = cfg.get("use_tmux_windows", False) and os.environ.get("TMUX") is not None

        if use_tmux:
            self._spawn_tmux(key, agent_name, bead_id, role, prompt, stage)
        else:
            self._spawn_background(key, agent_name, bead_id, role, prompt)

    def _spawn_tmux(self, key: str, agent_name: str, bead_id: str, role: str, prompt: str, stage: str):
        claude_cmd = "claude"
        if YOLO_MODE:
            claude_cmd += " --dangerously-skip-permissions"

        shell_cmd = f"export DEBUSSY_ROLE={role} DEBUSSY_BEAD={bead_id}; {claude_cmd}"

        try:
            subprocess.run([
                "tmux", "new-window", "-d", "-t", SESSION_NAME,
                "-n", agent_name, "bash", "-c", shell_cmd
            ], check=True)

            target = f"{SESSION_NAME}:{agent_name}"
            time.sleep(CLAUDE_STARTUP_DELAY)
            subprocess.run(
                ["tmux", "send-keys", "-l", "-t", target, prompt],
                check=True,
            )
            time.sleep(0.5)
            subprocess.run(
                ["tmux", "send-keys", "-t", target, "Enter"],
                check=True,
            )

            self.running[key] = AgentInfo(
                bead=bead_id, role=role, name=agent_name,
                spawned_stage=stage, tmux=True,
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

    def _enforce_single_stage(self):
        try:
            result = subprocess.run(
                ["bd", "list", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return
            beads = json.loads(result.stdout)
            if not isinstance(beads, list):
                return
        except Exception:
            return

        for bead in beads:
            labels = bead.get("labels", [])
            stages = [l for l in labels if l.startswith("stage:")]
            if len(stages) <= 1:
                continue

            bead_id = bead.get("id")
            keep = max(stages, key=lambda s: STAGE_ORDER.get(s, 0))
            cmd = ["bd", "update", bead_id]
            for stage in stages:
                if stage != keep:
                    cmd.extend(["--remove-label", stage])

            log(f"Cleaned {bead_id}: kept {keep}, removed {[s for s in stages if s != keep]}", "🧹")
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass

    def _unblock_ready(self):
        try:
            result = subprocess.run(
                ["bd", "list", "--status", "blocked", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return
            beads = json.loads(result.stdout)
            if not isinstance(beads, list):
                return
        except Exception:
            return

        for bead in beads:
            bead_id = bead.get("id")
            if not bead_id:
                continue
            labels = bead.get("labels", [])
            if not any(l.startswith("stage:") for l in labels):
                continue
            if _has_unresolved_deps(bead):
                continue
            try:
                subprocess.run(
                    ["bd", "update", bead_id, "--status", "open"],
                    capture_output=True, timeout=5,
                )
                log(f"Unblocked {bead_id}: deps resolved", "🔓")
            except Exception:
                pass

    def check_pipeline(self):
        for stage, role in STAGE_TO_ROLE.items():
            try:
                result = subprocess.run(
                    ["bd", "list", "--status", "open", "--label", stage, "--json"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    continue

                beads = json.loads(result.stdout)
                if not isinstance(beads, list):
                    continue

                for bead in beads:
                    bead_id = bead.get("id")
                    if not bead_id:
                        continue

                    if self.is_bead_running(bead_id):
                        continue

                    if self.failures.get(bead_id, 0) >= MAX_RETRIES:
                        continue

                    if bead.get("status") == "blocked":
                        continue

                    if bead.get("dependency_count", 0) > 0 and _has_unresolved_deps(bead):
                        continue

                    if role == "integrator" and self.has_running_role("integrator"):
                        if bead_id not in self.queued:
                            log(f"Queued: {bead_id} waiting for integrator", "⏳")
                            self.queued.add(bead_id)
                        continue

                    if self.is_at_capacity():
                        if bead_id not in self.queued:
                            log(f"Queued: {bead_id} waiting for agent slot", "⏳")
                            self.queued.add(bead_id)
                        continue

                    self.queued.discard(bead_id)
                    self.spawn_agent(role, bead_id, stage)

            except subprocess.TimeoutExpired:
                log(f"Timeout checking {stage}", "⚠️")
            except Exception as e:
                log(f"Error checking {stage}: {e}", "⚠️")

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
                    ["bd", "update", agent.bead, "--status", "open"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

    def _remove_agent(self, key: str, agent: AgentInfo):
        agent.cleanup()
        self.used_names.discard(agent.name)
        del self.running[key]

    def _ensure_stage_transition(self, agent: AgentInfo):
        if not agent.spawned_stage:
            return
        bead = _get_bead_json(agent.bead)
        if not bead:
            return

        labels = bead.get("labels", [])
        status = bead.get("status")
        has_rejected = "rejected" in labels
        stage_labels = [l for l in labels if l.startswith("stage:")]
        had_spawned_stage = agent.spawned_stage in stage_labels

        cmd = ["bd", "update", agent.bead]

        if status == "in_progress":
            cmd.extend(["--status", "open"])
            log(f"Agent left {agent.bead} as in_progress, resetting to open for retry", "⚠️")
        elif not had_spawned_stage:
            if has_rejected:
                cmd.extend(["--remove-label", "rejected"])
            log(f"Stage removed externally for {agent.bead}, skipping transition", "⏭️")
        else:
            for label in stage_labels:
                cmd.extend(["--remove-label", label])

            if has_rejected:
                cmd.extend(["--remove-label", "rejected"])
                cmd.extend(["--add-label", "stage:development"])
                log(f"Rejected {agent.bead}: {agent.spawned_stage} → stage:development", "↩️")
            elif status == "closed":
                log(f"Closed {agent.bead}: {agent.spawned_stage} complete", "✅")
            elif status == "blocked":
                log(f"Blocked {agent.bead}: parked for conductor", "⊘")
            elif status == "open":
                next_stage = NEXT_STAGE.get(agent.spawned_stage)
                if next_stage:
                    cmd.extend(["--add-label", next_stage])
                    log(f"Advancing {agent.bead}: {agent.spawned_stage} → {next_stage}", "⏩")

        if len(cmd) > 3:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass

    def cleanup_finished(self):
        cleaned = False
        for key, agent in list(self.running.items()):
            if agent.tmux and agent.is_alive(self._cached_windows):
                if agent.is_done():
                    log(f"{agent.name} completed {agent.bead}", "✅")
                    agent.stop()
                    self._ensure_stage_transition(agent)
                    self.failures.pop(agent.bead, None)
                    self._remove_agent(key, agent)
                    cleaned = True
                continue

            if not agent.is_alive(self._cached_windows):
                elapsed = time.time() - agent.started_at
                if elapsed < MIN_AGENT_RUNTIME:
                    self.failures[agent.bead] = self.failures.get(agent.bead, 0) + 1
                    log(f"{agent.name} crashed after {int(elapsed)}s on {agent.bead} (attempt {self.failures[agent.bead]}/{MAX_RETRIES})", "💥")
                else:
                    self._ensure_stage_transition(agent)
                    self.failures.pop(agent.bead, None)
                    log(f"{agent.name} finished {agent.bead}", "🛑")
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
                self._enforce_single_stage()
                self._unblock_ready()
                self.check_pipeline()
                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._log_heartbeat()
            except Exception as e:
                log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
