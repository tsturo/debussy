"""Mailbox watcher - spawns agents on demand."""

import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path

from .config import AGENTS, POLL_INTERVAL, YOLO_MODE, MAILBOX_ROOT
from .mailbox import Mailbox

PIPELINE_AGENTS = {
    "testing": "tester",
    "reviewing": "reviewer",
    "merging": "integrator",
    "acceptance": "tester",
}


class Watcher:
    def __init__(self):
        self.running_agents: dict[str, dict] = {}
        self.should_exit = False

    def log(self, msg: str, icon: str = "•"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {icon} {msg}")

    def start_agent(self, agent_name: str, message_file: Path):
        if agent_name in self.running_agents:
            proc = self.running_agents[agent_name]["proc"]
            if proc.poll() is None:
                return

        task_name = message_file.stem
        self.log(f"Starting @{agent_name} ({task_name})", "🚀")

        role = agent_name.rstrip('2')
        role_file = Path(f".claude/subagents/{role}.md")

        if role == "developer":
            prompt = f"""You are @{agent_name} - a developer.

Read your task: cat {message_file}
Then: bd show <bead-id>

WORKFLOW:
1. bd update <bead-id> --status in-progress
2. Create feature branch: git checkout -b feature/<bead-id>
3. Implement the task
4. Commit and push your changes
5. IMPORTANT: bd update <bead-id> --status testing
6. debussy send conductor "Done <bead-id>" -b "Ready for testing"
7. Exit

CRITICAL: Set status to "testing" when done, NOT "done". Pipeline continues automatically."""
        else:
            prompt = f"""You are @{agent_name}. Read {role_file} for your role.

Read your task: cat {message_file}
Then: bd show <bead-id>

1. bd update <bead-id> --status in-progress
2. Do the work as described in your role file
3. Update status and notify conductor
4. Exit when finished"""

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd())
            self.running_agents[agent_name] = {"proc": proc, "task": task_name}
        except Exception as e:
            self.log(f"Failed to start {agent_name}: {e}", "✗")

    def check_mailboxes(self):
        for agent_name in AGENTS:
            try:
                mailbox = Mailbox(agent_name)
                if not mailbox.inbox.exists():
                    continue

                messages = list(mailbox.inbox.glob("*.json"))
                if messages:
                    if agent_name not in self.running_agents:
                        self.log(f"@{agent_name} has {len(messages)} message(s)", "📬")
                        self.start_agent(agent_name, sorted(messages)[0])
            except Exception as e:
                self.log(f"Error checking mailbox for {agent_name}: {e}", "⚠️")

    def check_pipeline(self):
        for status, agent_name in PIPELINE_AGENTS.items():
            try:
                if agent_name in self.running_agents:
                    proc = self.running_agents[agent_name]["proc"]
                    if proc.poll() is None:
                        continue

                result = subprocess.run(
                    ["bd", "list", "--status", status],
                    capture_output=True, text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    continue
                if not result.stdout or not result.stdout.strip():
                    continue

                lines = result.stdout.strip().split('\n')
                if not lines or not lines[0]:
                    continue

                parts = lines[0].split()
                if not parts:
                    continue

                bead_id = parts[0]
                if bead_id and agent_name not in self.running_agents:
                    self.log(f"Task {bead_id} ready for @{agent_name} ({status})", "📋")
                    self.start_pipeline_agent(agent_name, bead_id, status)
            except subprocess.TimeoutExpired:
                self.log(f"Timeout checking {status} status", "⚠️")
            except Exception as e:
                self.log(f"Error checking pipeline {status}: {e}", "⚠️")

    def start_pipeline_agent(self, agent_name: str, bead_id: str, status: str):
        if agent_name in self.running_agents:
            proc = self.running_agents[agent_name]["proc"]
            if proc.poll() is None:
                return

        self.log(f"Starting @{agent_name} for {bead_id} (status={status})", "🚀")

        if agent_name == "tester" and status == "testing":
            prompt = f"""You are @tester. Task {bead_id} needs testing.

1. bd show {bead_id}
2. git checkout feature/{bead_id} (or find the branch)
3. Run tests, check functionality
4. If PASS: bd update {bead_id} --status reviewing
5. If FAIL: bd update {bead_id} --status in-progress, notify developer
6. debussy send conductor "Tested {bead_id}" -b "Status: reviewing/failed"
7. Exit"""
        elif agent_name == "tester" and status == "acceptance":
            prompt = f"""You are @tester. Task {bead_id} needs acceptance testing (post-merge).

1. bd show {bead_id}
2. git checkout develop && git pull
3. Run full test suite, verify feature works
4. If PASS: bd update {bead_id} --status done
5. If FAIL: bd update {bead_id} --status in-progress, notify developer
6. debussy send conductor "Acceptance {bead_id}" -b "Status: done/failed"
7. Exit"""
        elif agent_name == "reviewer":
            prompt = f"""You are @reviewer. Task {bead_id} needs code review.

1. bd show {bead_id}
2. git checkout feature/{bead_id}
3. Review code: git diff develop...HEAD
4. If APPROVED: bd update {bead_id} --status merging
5. If CHANGES NEEDED: bd update {bead_id} --status in-progress, notify developer
6. debussy send conductor "Reviewed {bead_id}" -b "Status: merging/changes-needed"
7. Exit"""
        elif agent_name == "integrator":
            prompt = f"""You are @integrator. Task {bead_id} needs to be merged.

1. bd show {bead_id}
2. git checkout develop && git pull
3. git merge feature/{bead_id} --no-ff
4. Resolve conflicts if any
5. git push origin develop
6. bd update {bead_id} --status acceptance
7. debussy send conductor "Merged {bead_id}" -b "Status: acceptance"
8. Exit"""
        else:
            role_file = Path(f".claude/subagents/{agent_name}.md")
            prompt = f"""You are @{agent_name}. Task {bead_id} is ready (status={status}).

1. bd show {bead_id}
2. Do the work
3. Update status when done
4. debussy send conductor "Done {bead_id}"
5. Exit"""

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd())
            self.running_agents[agent_name] = {"proc": proc, "task": bead_id}
        except Exception as e:
            self.log(f"Failed to start {agent_name}: {e}", "✗")

    def check_agent_status(self):
        for agent_name, info in list(self.running_agents.items()):
            proc = info["proc"]
            if proc.poll() is not None:
                self.log(f"@{agent_name} finished (code {proc.returncode})", "🛑")
                del self.running_agents[agent_name]

    def signal_handler(self, signum, frame):
        self.should_exit = True

    def run(self):
        import time

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.log(f"Watcher started (poll every {POLL_INTERVAL}s)", "👀")

        MAILBOX_ROOT.mkdir(parents=True, exist_ok=True)
        for agent in AGENTS + ["conductor"]:
            Mailbox(agent).ensure_dirs()

        tick = 0
        while not self.should_exit:
            try:
                self.check_agent_status()
                self.check_mailboxes()
                self.check_pipeline()

                tick += 1
                if tick % 12 == 0:
                    if self.running_agents:
                        self.log("Running:", "🔄")
                        for name, info in self.running_agents.items():
                            self.log(f"  @{name}: {info['task']}", "")
                    else:
                        self.log("Idle - no agents running", "💤")
            except Exception as e:
                self.log(f"Error in watcher loop: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self.log("Stopping agents...", "🛑")
        for name, info in self.running_agents.items():
            info["proc"].terminate()

        self.log("Watcher stopped")
