"""Watcher - spawns agents based on bead status."""

import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path

os.environ.pop("ANTHROPIC_API_KEY", None)

from .config import POLL_INTERVAL, YOLO_MODE, SINGLETON_ROLES

STATUS_TO_ROLE = {
    "open": "developer",
    "reviewing": "reviewer",
    "testing": "tester",
    "merging": "integrator",
    "acceptance": "tester",
}

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


class Watcher:
    def __init__(self):
        self.running: dict[str, dict] = {}
        self.queued: set[str] = set()
        self.used_names: set[str] = set()
        self.should_exit = False

    def get_agent_name(self, role: str) -> str:
        import random
        available = [n for n in COMPOSERS if f"{role}-{n}" not in self.used_names]
        if available:
            name = random.choice(available)
            full_name = f"{role}-{name}"
            self.used_names.add(full_name)
            return full_name
        return f"{role}-{len(self.used_names)}"

    def log(self, msg: str, icon: str = "•"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {icon} {msg}")

    def is_bead_running(self, bead_id: str) -> bool:
        for info in self.running.values():
            if info.get("bead") == bead_id:
                proc = info["proc"]
                if proc.poll() is None:
                    return True
        return False

    def count_running_by_role(self, role: str) -> int:
        count = 0
        for info in self.running.values():
            if info.get("role") == role:
                proc = info["proc"]
                if proc.poll() is None:
                    count += 1
        return count

    def count_total_running(self) -> int:
        count = 0
        for info in self.running.values():
            if info["proc"].poll() is None:
                count += 1
        return count

    def get_dynamic_max(self, role: str) -> int:
        from .config import get_config, SINGLETON_ROLES
        if role in SINGLETON_ROLES:
            return 1
        cfg = get_config()
        base_max = cfg.get(f"max_{role}s", 3)
        max_total = cfg.get("max_total_agents", 6)
        total = self.count_total_running()
        if total >= max_total:
            return 1
        if total >= max_total - 2:
            return min(base_max, 2)
        return base_max

    def is_blocked(self, bead_id: str) -> bool:
        try:
            result = subprocess.run(
                ["bd", "show", bead_id],
                capture_output=True, text=True, timeout=5
            )
            return "Blocked by" in result.stdout
        except Exception:
            return False

    def get_prompt(self, role: str, bead_id: str, status: str) -> str:
        if role == "developer":
            return f"""You are a developer. Work on bead {bead_id}.

1. bd show {bead_id}
2. git checkout -b feature/{bead_id} (or checkout existing branch)
3. Implement the task
4. Commit and push changes
5. bd update {bead_id} --status reviewing
6. Exit

IMPORTANT: Do NOT use "bd close". Use "bd update {bead_id} --status reviewing" to pass to reviewer."""

        elif role == "tester" and status == "testing":
            return f"""You are a tester. Test bead {bead_id}.

1. bd show {bead_id}
2. git checkout feature/{bead_id}
3. Review the changes (git diff develop...HEAD)
4. Write automated tests for the new functionality
5. Run all tests
6. Commit and push the tests

If ALL TESTS PASS:
  bd update {bead_id} --status merging
  Exit

If TESTS FAIL:
  bd comment {bead_id} "Tests failed: [details]"
  bd update {bead_id} --status open
  Exit

IMPORTANT: Always write tests before approving. No untested code passes."""

        elif role == "tester" and status == "acceptance":
            return f"""You are a tester. Acceptance test for bead {bead_id} (post-merge).

1. bd show {bead_id}
2. git checkout develop && git pull
3. Run full test suite, verify feature works

If PASS:
  bd update {bead_id} --status done
  Exit

If FAIL:
  bd comment {bead_id} "Acceptance failed: [details]"
  bd update {bead_id} --status open
  Exit"""

        elif role == "reviewer":
            return f"""You are a code reviewer. Review bead {bead_id}.

1. bd show {bead_id}
2. git checkout feature/{bead_id}
3. Review: git diff develop...HEAD

If APPROVED:
  bd update {bead_id} --status testing
  Exit

If CHANGES NEEDED:
  bd comment {bead_id} "Review feedback: [details]"
  bd update {bead_id} --status open
  Exit"""

        elif role == "integrator":
            return f"""You are an integrator. Merge bead {bead_id}.

1. bd show {bead_id}
2. git checkout develop && git pull
3. git merge feature/{bead_id} --no-ff
4. Resolve conflicts if any
5. Run tests
6. git push origin develop
7. git branch -d feature/{bead_id}
8. git push origin --delete feature/{bead_id}
9. bd update {bead_id} --status acceptance
10. Exit"""

        return f"""You are a {role}. Work on bead {bead_id} (status={status}).

1. bd show {bead_id}
2. Do the work
3. Update status when done
4. Exit"""

    def extract_bead_id(self, line: str) -> str | None:
        parts = line.split()
        if len(parts) < 2:
            return None
        candidate = parts[1]
        if candidate.startswith("["):
            return parts[0] if not parts[0].startswith(("○", "●", "◐", "✓", "✗")) else None
        return candidate

    def is_epic_or_feature(self, line: str) -> bool:
        return "[epic]" in line.lower() or "[feature]" in line.lower()

    def spawn_agent(self, role: str, bead_id: str, status: str):
        key = f"{role}:{bead_id}"

        if key in self.running:
            proc = self.running[key]["proc"]
            if proc.poll() is None:
                return

        agent_name = self.get_agent_name(role)
        self.log(f"Spawning {agent_name} for {bead_id}", "🚀")

        prompt = self.get_prompt(role, bead_id, status)

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        logs_dir = Path(".debussy/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / f"{agent_name}.log"

        try:
            log_handle = open(log_file, "w", buffering=1)
            proc = subprocess.Popen(
                cmd, cwd=os.getcwd(),
                stdout=log_handle, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            self.running[key] = {"proc": proc, "bead": bead_id, "role": role, "name": agent_name, "log": str(log_file), "log_handle": log_handle}
        except Exception as e:
            self.log(f"Failed to spawn {role}: {e}", "✗")

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

                    max_allowed = self.get_dynamic_max(role)
                    if self.count_running_by_role(role) >= max_allowed:
                        if bead_id not in self.queued:
                            self.log(f"Queued: {bead_id} waiting for {role} slot", "⏳")
                            self.queued.add(bead_id)
                        continue

                    self.queued.discard(bead_id)
                    self.spawn_agent(role, bead_id, status)

            except subprocess.TimeoutExpired:
                self.log(f"Timeout checking {status}", "⚠️")
            except Exception as e:
                self.log(f"Error checking {status}: {e}", "⚠️")

    def cleanup_finished(self):
        for key, info in list(self.running.items()):
            proc = info["proc"]
            if proc.poll() is not None:
                name = info.get("name", info.get("role", "agent"))
                bead = info.get("bead", "")
                if "log_handle" in info:
                    info["log_handle"].close()
                self.log(f"{name} finished {bead} (exit {proc.returncode})", "🛑")
                self.used_names.discard(name)
                del self.running[key]

    def signal_handler(self, signum, frame):
        self.should_exit = True

    def run(self):
        import time

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.log(f"Watcher started (poll every {POLL_INTERVAL}s)", "👀")

        tick = 0
        while not self.should_exit:
            try:
                self.cleanup_finished()
                self.check_pipeline()

                tick += 1
                if tick % 12 == 0:
                    if self.running:
                        self.log("Active:", "🔄")
                        for info in self.running.values():
                            name = info.get("name", info["role"])
                            self.log(f"  {name} → {info['bead']}", "")
                    else:
                        self.log("Idle", "💤")
            except Exception as e:
                self.log(f"Error: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self.log("Stopping agents...", "🛑")
        for info in self.running.values():
            info["proc"].terminate()

        self.log("Watcher stopped")
