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
        self.running_agents: dict[str, subprocess.Popen] = {}
        self.should_exit = False

    def log(self, msg: str, icon: str = "•"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {icon} {msg}")

    def start_agent(self, agent_name: str, message_file: Path):
        if agent_name in self.running_agents:
            proc = self.running_agents[agent_name]
            if proc.poll() is None:
                return

        self.log(f"Starting @{agent_name}", "🚀")

        role = agent_name.rstrip('2')
        role_file = Path(f".claude/subagents/{role}.md")

        prompt = f"""You are @{agent_name}. Read {role_file} for your role.

You have a task in your mailbox. Process it:
1. Read message: cat {message_file}
2. Get bead: bd show <bead-id>
3. Mark in progress: bd update <bead-id> --status in-progress
4. Do the work as described in your role file
5. Update status and notify conductor (see role file)
6. Exit when finished

Start by reading your task."""

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd())
            self.running_agents[agent_name] = proc
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
                    proc = self.running_agents[agent_name]
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
            proc = self.running_agents[agent_name]
            if proc.poll() is None:
                return

        self.log(f"Starting @{agent_name} for {bead_id} (status={status})", "🚀")

        role_file = Path(f".claude/subagents/{agent_name}.md")

        prompt = f"""You are @{agent_name}. Read {role_file} for your role.

Task {bead_id} is ready for you (status={status}).

1. Get task details: bd show {bead_id}
2. Do the work as described in your role file
3. Update status when done
4. Notify conductor
5. Exit when finished

Start by reading the task."""

        cmd = ["claude"]
        if YOLO_MODE:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])

        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd())
            self.running_agents[agent_name] = proc
        except Exception as e:
            self.log(f"Failed to start {agent_name}: {e}", "✗")

    def check_agent_status(self):
        for agent_name, proc in list(self.running_agents.items()):
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
                    running = list(self.running_agents.keys())
                    if running:
                        self.log(f"Running: {', '.join(running)}", "🔄")
                    else:
                        self.log("Idle - no agents running", "💤")
            except Exception as e:
                self.log(f"Error in watcher loop: {e}", "⚠️")
            time.sleep(POLL_INTERVAL)

        self.log("Stopping agents...", "🛑")
        for name, proc in self.running_agents.items():
            proc.terminate()

        self.log("Watcher stopped")
