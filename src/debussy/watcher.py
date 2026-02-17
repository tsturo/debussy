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
    HEARTBEAT_TICKS, NEXT_STAGE, STAGE_TO_ROLE, atomic_write,
    get_config, log,
)
from .prompts import get_prompt
from .worktree import cleanup_orphaned_branches, cleanup_stale_worktrees, create_worktree, delete_branch, remove_worktree

EVENTS_FILE = Path(".debussy/pipeline_events.jsonl")


def _record_event(bead_id: str, event: str, **kwargs):
    entry = {"ts": time.time(), "bead": bead_id, "event": event, **kwargs}
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


MIN_AGENT_RUNTIME = 30
MAX_RETRIES = 3
MAX_REJECTIONS = 5
REJECTION_COOLDOWN = 60

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


def _branch_has_commits(bead_id: str, base: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base}..origin/feature/{bead_id}"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and int(result.stdout.strip()) > 0
    except Exception:
        return True


def _has_unresolved_deps(bead: dict) -> bool:
    for dep in bead.get("dependencies", []):
        dep_id = dep.get("depends_on_id") or dep.get("id")
        if not dep_id:
            continue
        status = dep.get("status") or _get_bead_status(dep_id)
        if status != "closed":
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
    worktree_path: str = ""

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
        self.empty_branch_retries: dict[str, int] = {}
        self.rejections: dict[str, int] = {}
        self.cooldowns: dict[str, float] = {}
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
        except Exception:
            pass

    def _save_rejections(self):
        try:
            atomic_write(self._rejections_file, json.dumps(self.rejections))
        except Exception:
            pass

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
                "worktree_path": agent.worktree_path,
                "started_at": agent.started_at,
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
        max_total = get_config().get("max_total_agents", 8)
        return len(self._alive_agents()) >= max_total

    def has_running_role(self, role: str) -> bool:
        return any(a.role == role for a in self._alive_agents())

    def _create_agent_worktree(self, role: str, bead_id: str, agent_name: str) -> str:
        if role == "investigator":
            return ""
        cfg = get_config()
        base = cfg.get("base_branch", "master")
        try:
            subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
        except Exception:
            pass
        try:
            if role == "developer":
                wt = create_worktree(agent_name, f"feature/{bead_id}", start_point=f"origin/{base}", new_branch=True)
            elif role == "reviewer":
                wt = create_worktree(agent_name, f"origin/feature/{bead_id}", detach=True)
            elif role in ("integrator", "tester"):
                wt = create_worktree(agent_name, f"origin/{base}", detach=True)
            else:
                return ""
            return str(wt)
        except Exception as e:
            log(f"Failed to create worktree for {agent_name}: {e}", "⚠️")
            return ""

    def spawn_agent(self, role: str, bead_id: str, stage: str):
        key = f"{role}:{bead_id}"

        if key in self.running and self.running[key].is_alive(self._cached_windows):
            return

        agent_name = self.get_agent_name(role)
        log(f"Spawning {agent_name} for {bead_id}", "🚀")
        _record_event(bead_id, "spawn", stage=stage, agent=agent_name)

        worktree_path = self._create_agent_worktree(role, bead_id, agent_name)

        prompt = get_prompt(role, bead_id, stage)

        cfg = get_config()
        use_tmux = cfg.get("use_tmux_windows", False) and os.environ.get("TMUX") is not None

        if use_tmux:
            self._spawn_tmux(key, agent_name, bead_id, role, prompt, stage, worktree_path)
        else:
            self._spawn_background(key, agent_name, bead_id, role, prompt, worktree_path)

    def _spawn_tmux(self, key: str, agent_name: str, bead_id: str, role: str, prompt: str, stage: str, worktree_path: str = ""):
        claude_cmd = "claude"
        if YOLO_MODE:
            claude_cmd += " --dangerously-skip-permissions"

        cd_prefix = f"cd '{worktree_path}' && " if worktree_path else ""
        shell_cmd = f"{cd_prefix}export DEBUSSY_ROLE={role} DEBUSSY_BEAD={bead_id}; {claude_cmd}"

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
                spawned_stage=stage, tmux=True, worktree_path=worktree_path,
            )
            if self._cached_windows is not None:
                self._cached_windows.add(agent_name)
            self.save_state()
        except Exception as e:
            log(f"Failed to spawn tmux window: {e}", "✗")

    def _spawn_background(self, key: str, agent_name: str, bead_id: str, role: str, prompt: str, worktree_path: str = ""):
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
            cwd = worktree_path if worktree_path else os.getcwd()
            log_handle = open(log_file, "wb", buffering=0)
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env,
                stdout=log_handle, stderr=subprocess.STDOUT,
                bufsize=0
            )
            self.running[key] = AgentInfo(
                bead=bead_id, role=role, name=agent_name,
                proc=proc, log_path=str(log_file), log_handle=log_handle,
                worktree_path=worktree_path,
            )
            self.save_state()
        except Exception as e:
            log(f"Failed to spawn {role}: {e}", "✗")

    def _reset_orphaned(self):
        try:
            result = subprocess.run(
                ["bd", "list", "--status", "in_progress", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return
            beads = json.loads(result.stdout)
            if not isinstance(beads, list):
                return
        except Exception:
            return

        running_beads = {a.bead for a in self.running.values()}
        for bead in beads:
            bead_id = bead.get("id")
            if not bead_id or bead_id in running_beads:
                continue
            labels = bead.get("labels", [])
            stage_labels = [l for l in labels if l.startswith("stage:")]
            if not stage_labels:
                continue
            full_bead = _get_bead_json(bead_id)
            real_labels = full_bead.get("labels", []) if full_bead else labels
            real_stages = [l for l in real_labels if l.startswith("stage:")]
            cmd = ["bd", "update", bead_id, "--status", "open"]
            for label in real_stages[1:]:
                cmd.extend(["--remove-label", label])
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
                log(f"Reset orphaned {bead_id}: no agent running", "👻")
            except Exception:
                pass

    def _release_ready(self):
        for status in ("blocked", "open"):
            try:
                result = subprocess.run(
                    ["bd", "list", "--status", status, "--json"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    continue
                beads = json.loads(result.stdout)
                if not isinstance(beads, list):
                    continue
            except Exception:
                continue

            for bead in beads:
                bead_id = bead.get("id")
                if not bead_id or bead.get("dependency_count", 0) == 0:
                    continue
                full_bead = _get_bead_json(bead_id)
                if not full_bead or _has_unresolved_deps(full_bead):
                    continue

                labels = full_bead.get("labels", [])
                has_stage = any(l.startswith("stage:") for l in labels)
                cmd = ["bd", "update", bead_id]

                if status == "blocked":
                    cmd.extend(["--status", "open"])

                if not has_stage:
                    cmd.extend(["--add-label", "stage:development"])

                if len(cmd) <= 3:
                    continue

                try:
                    subprocess.run(cmd, capture_output=True, timeout=5)
                    if has_stage:
                        log(f"Unblocked {bead_id}: deps resolved", "🔓")
                        _record_event(bead_id, "unblock")
                    else:
                        log(f"Released {bead_id}: deps resolved → stage:development", "🔓")
                        _record_event(bead_id, "release", stage="stage:development")
                    self._verify_single_stage(bead_id)
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

                beads.sort(key=lambda b: b.get("issue_type") != "bug")

                for bead in beads:
                    bead_id = bead.get("id")
                    if not bead_id:
                        continue

                    if self.is_bead_running(bead_id):
                        continue

                    cooldown_until = self.cooldowns.get(bead_id, 0)
                    if cooldown_until and time.time() - cooldown_until < REJECTION_COOLDOWN:
                        continue

                    if self.failures.get(bead_id, 0) >= MAX_RETRIES:
                        continue

                    if bead.get("status") == "blocked":
                        continue

                    if bead.get("dependency_count", 0) > 0:
                        full_bead = _get_bead_json(bead_id)
                        if not full_bead or _has_unresolved_deps(full_bead):
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
            _record_event(agent.bead, "timeout", stage=agent.spawned_stage, agent=agent.name)
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
            self._remove_agent(key, agent)

    def _remove_agent(self, key: str, agent: AgentInfo):
        agent.cleanup()
        if agent.worktree_path:
            try:
                remove_worktree(agent.name)
            except Exception as e:
                log(f"Failed to remove worktree for {agent.name}: {e}", "⚠️")
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
            for label in stage_labels[1:]:
                cmd.extend(["--remove-label", label])
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
                self.rejections[agent.bead] = self.rejections.get(agent.bead, 0) + 1
                count = self.rejections[agent.bead]
                if count >= MAX_REJECTIONS:
                    cmd.extend(["--status", "blocked"])
                    log(f"Blocked {agent.bead}: rejected {count} times, needs conductor", "🚫")
                    _record_event(agent.bead, "loop_blocked", stage=agent.spawned_stage, rejections=count)
                    try:
                        subprocess.run(
                            ["bd", "comment", agent.bead, f"Blocked after {count} rejection loops — needs conductor intervention"],
                            capture_output=True, timeout=5,
                        )
                    except Exception:
                        pass
                else:
                    cmd.extend(["--add-label", "stage:development"])
                    self.cooldowns[agent.bead] = time.time()
                    log(f"Rejected {agent.bead} ({count}/{MAX_REJECTIONS}): {agent.spawned_stage} → stage:development (cooldown {REJECTION_COOLDOWN}s)", "↩️")
                self._save_rejections()
                _record_event(agent.bead, "reject", **{"from": agent.spawned_stage, "to": "stage:development"})
            elif status == "closed":
                self.rejections.pop(agent.bead, None)
                self._save_rejections()
                delete_branch(f"feature/{agent.bead}")
                log(f"Closed {agent.bead}: {agent.spawned_stage} complete", "✅")
                _record_event(agent.bead, "close", stage=agent.spawned_stage)
            elif status == "blocked":
                log(f"Blocked {agent.bead}: parked for conductor", "⊘")
                _record_event(agent.bead, "block", stage=agent.spawned_stage)
            elif status == "open":
                next_stage = NEXT_STAGE.get(agent.spawned_stage)
                if next_stage and agent.spawned_stage == "stage:development":
                    base = get_config().get("base_branch", "master")
                    if not _branch_has_commits(agent.bead, base):
                        self.empty_branch_retries[agent.bead] = self.empty_branch_retries.get(agent.bead, 0) + 1
                        count = self.empty_branch_retries[agent.bead]
                        if count >= MAX_RETRIES:
                            cmd.extend(["--status", "blocked"])
                            log(f"Blocked {agent.bead}: empty branch after {count} attempts, needs conductor", "🚫")
                            _record_event(agent.bead, "empty_branch_blocked", stage=agent.spawned_stage, retries=count)
                            try:
                                subprocess.run(
                                    ["bd", "comment", agent.bead, f"Blocked after {count} empty-branch retries — needs conductor intervention"],
                                    capture_output=True, timeout=5,
                                )
                            except Exception:
                                pass
                        else:
                            cmd.extend(["--add-label", "stage:development"])
                            log(f"No commits on feature/{agent.bead} — retry {count}/{MAX_RETRIES}", "⚠️")
                            _record_event(agent.bead, "empty_branch", stage=agent.spawned_stage, retry=count)
                        next_stage = None
                if next_stage:
                    self.empty_branch_retries.pop(agent.bead, None)
                    cmd.extend(["--add-label", next_stage])
                    log(f"Advancing {agent.bead}: {agent.spawned_stage} → {next_stage}", "⏩")
                    _record_event(agent.bead, "advance", **{"from": agent.spawned_stage, "to": next_stage})

        if len(cmd) > 3:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass
            self._verify_single_stage(agent.bead)

    def _verify_single_stage(self, bead_id: str):
        bead = _get_bead_json(bead_id)
        if not bead:
            return
        stages = [l for l in bead.get("labels", []) if l.startswith("stage:")]
        if len(stages) <= 1:
            return
        cmd = ["bd", "update", bead_id]
        for label in stages[1:]:
            cmd.extend(["--remove-label", label])
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            log(f"Fixed {bead_id}: removed {len(stages)-1} extra stage label(s), kept {stages[0]}", "🔧")
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
                self._reset_orphaned()
                self._release_ready()
                self.check_pipeline()
                self.save_state()

                tick += 1
                if tick % HEARTBEAT_TICKS == 0:
                    self._log_heartbeat()
            except Exception as e:
                log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self._shutdown()
