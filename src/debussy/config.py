"""Configuration for Debussy."""

from pathlib import Path

MAILBOX_ROOT = Path(".claude/mailbox")
AGENTS = ["architect", "developer", "developer2", "tester", "reviewer", "integrator"]
POLL_INTERVAL = 5
YOLO_MODE = True
SESSION_NAME = "debussy"
