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
        self.running: dict[str, dict] = {}
        self.should_exit = False

    def log(self, msg: str, icon: str = "•"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {icon} {msg}")

    def is_task_running(self, task_id: str) -> bool:
        for key, info in self.running.items():
            if info.get("task") == task_id:
                proc = info["proc"]
                if proc.poll() is None:
                    return True
        return False

    def start_agent(self, agent_name: str, message_file: Path):
        task_name = message_file.stem
        key = f"{agent_name}:{task_name}"

        if key in self.running:
            proc = self.running[key]["proc"]
            if proc.poll() is None:
                return

        try:
            message_content = message_file.read_text()
        except Exception:
            message_content = f"Task: {task_name}"

        self.log(f"Starting @{agent_name} ({task_name})", "🚀")

        role = agent_name.rstrip('2')

        if role == "developer":
            prompt = f"""You are @{agent_name} - a developer.

YOUR TASK:
{message_content}

WORKFLOW:
1. bd show <bead-id> to get details
2. bd update <bead-id> --status in-progress
3. Create feature branch: git checkout -b feature/<bead-id>
4. Implement the task
5. Commit and push your changes
6. IMPORTANT: bd update <bead-id> --status testing
7. debussy send conductor "Done <bead-id>" -b "Ready for testing"
8. Exit

CRITICAL: Set status to "testing" when done, NOT "done". Pipeline continues automatically."""
        else:
            prompt = f"""You are @{agent_name}.

YOUR TASK:
{message_content}

1. bd show <bead-id> to get details
2. bd update <bead-id> --status in-progress
3. Do the work
4. Update status and notify conductor
5. Exit when finished"""

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd())
            self.running[key] = {"proc": proc, "task": task_name, "agent": agent_name}
            message_file.unlink(missing_ok=True)
        except Exception as e:
            self.log(f"Failed to start {agent_name}: {e}", "✗")

    def check_mailboxes(self):
        for agent_name in AGENTS:
            try:
                mailbox = Mailbox(agent_name)
                if not mailbox.inbox.exists():
                    continue

                messages = list(mailbox.inbox.glob("*.json"))
                for msg_file in sorted(messages):
                    task_id = msg_file.stem
                    if not self.is_task_running(task_id):
                        self.log(f"@{agent_name} has message: {task_id}", "📬")
                        self.start_agent(agent_name, msg_file)
            except Exception as e:
                self.log(f"Error checking mailbox for {agent_name}: {e}", "⚠️")

    def check_pipeline(self):
        for status, agent_name in PIPELINE_AGENTS.items():
            try:
                result = subprocess.run(
                    ["bd", "list", "--status", status],
                    capture_output=True, text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    continue
                if not result.stdout or not result.stdout.strip():
                    continue

                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue
                    parts = line.split()
                    if not parts:
                        continue

                    bead_id = parts[0]
                    if bead_id and not self.is_task_running(bead_id):
                        self.log(f"Task {bead_id} ready for @{agent_name} ({status})", "📋")
                        self.start_pipeline_agent(agent_name, bead_id, status)
            except subprocess.TimeoutExpired:
                self.log(f"Timeout checking {status} status", "⚠️")
            except Exception as e:
                self.log(f"Error checking pipeline {status}: {e}", "⚠️")

    def start_pipeline_agent(self, agent_name: str, bead_id: str, status: str):
        key = f"{agent_name}:{bead_id}"

        if key in self.running:
            proc = self.running[key]["proc"]
            if proc.poll() is None:
                return

        self.log(f"Starting @{agent_name} for {bead_id} (status={status})", "🚀")

        if agent_name == "tester" and status == "testing":
            prompt = f"""You are @tester. Task {bead_id} needs testing.

1. bd show {bead_id}
2. git checkout feature/{bead_id} (or find the branch)
3. Run tests, check functionality

If PASS:
  bd update {bead_id} --status reviewing
  debussy send conductor "PASS {bead_id}" -b "Tests passed. Status: reviewing"

If FAIL:
  bd update {bead_id} --status in-progress
  debussy send developer "BUG {bead_id}" -b "Tests failed: [describe issue]"
  debussy send conductor "FAIL {bead_id}" -b "Tests failed, sent to developer"

Exit when done."""
        elif agent_name == "tester" and status == "acceptance":
            prompt = f"""You are @tester. Task {bead_id} needs acceptance testing (post-merge).

1. bd show {bead_id}
2. git checkout develop && git pull
3. Run full test suite, verify feature works

If PASS:
  bd update {bead_id} --status done
  debussy send conductor "ACCEPTED {bead_id}" -b "Acceptance passed. Done!"

If FAIL:
  bd update {bead_id} --status in-progress
  debussy send developer "REGRESSION {bead_id}" -b "Acceptance failed: [describe issue]"
  debussy send conductor "REJECTED {bead_id}" -b "Acceptance failed, sent to developer"

Exit when done."""
        elif agent_name == "reviewer":
            prompt = f"""You are @reviewer. Task {bead_id} needs code review.

1. bd show {bead_id}
2. git checkout feature/{bead_id}
3. Review code: git diff develop...HEAD

If APPROVED:
  bd update {bead_id} --status merging
  debussy send conductor "APPROVED {bead_id}" -b "Code review passed. Status: merging"

If CHANGES NEEDED:
  bd update {bead_id} --status in-progress
  debussy send developer "CHANGES {bead_id}" -b "Review feedback: [describe issues]"
  debussy send conductor "CHANGES {bead_id}" -b "Changes requested, sent to developer"

Exit when done."""
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
            self.running[key] = {"proc": proc, "task": bead_id, "agent": agent_name}
        except Exception as e:
            self.log(f"Failed to start {agent_name}: {e}", "✗")

    def check_agent_status(self):
        for key, info in list(self.running.items()):
            proc = info["proc"]
            if proc.poll() is not None:
                agent = info.get("agent", key)
                task = info.get("task", "")
                self.log(f"@{agent} finished {task} (code {proc.returncode})", "🛑")
                del self.running[key]

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
                    if self.running:
                        self.log("Running:", "🔄")
                        for key, info in self.running.items():
                            self.log(f"  @{info['agent']}: {info['task']}", "")
                    else:
                        self.log("Idle - no agents running", "💤")
            except Exception as e:
                self.log(f"Error in watcher loop: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self.log("Stopping agents...", "🛑")
        for key, info in self.running.items():
            info["proc"].terminate()

        self.log("Watcher stopped")
