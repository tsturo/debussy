"""Configuration for Debussy."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

POLL_INTERVAL = 5
HEARTBEAT_TICKS = 12
CLAUDE_STARTUP_DELAY = 6
COMMENT_TRUNCATE_LEN = 80
YOLO_MODE = True
SESSION_NAME = "debussy"
SINGLETON_ROLES = ["integrator"]
AGENT_TIMEOUT = 900

CONFIG_DIR = Path(".debussy")
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "max_developers": 3,
    "max_investigators": 3,
    "max_testers": 3,
    "max_reviewers": 3,
    "max_total_agents": 6,
    "use_tmux_windows": True,
}

STATUS_TO_ROLE = {
    "development": "developer",
    "investigating": "investigator",
    "consolidating": "investigator",
    "reviewing": "reviewer",
    "testing": "tester",
    "merging": "integrator",
    "acceptance": "tester",
}

PIPELINE_STATUSES = "development,investigating,consolidating,testing,reviewing,merging,acceptance,done"


def log(msg: str, icon: str = "•"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} {icon} {msg}")


def atomic_write(path: Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def get_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return {**DEFAULTS, **cfg}
    except Exception:
        return DEFAULTS.copy()


def set_config(key: str, value):
    CONFIG_DIR.mkdir(exist_ok=True)
    cfg = get_config()
    cfg[key] = value
    atomic_write(CONFIG_FILE, json.dumps(cfg, indent=2))


def get_base_branch() -> str | None:
    return get_config().get("base_branch")


def parse_value(value: str) -> str | bool | int:
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    try:
        return int(value)
    except ValueError:
        return value
