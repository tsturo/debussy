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
AGENT_TIMEOUT = 3600

STAGE_DEVELOPMENT = "stage:development"
STAGE_REVIEWING = "stage:reviewing"
STAGE_SECURITY_REVIEW = "stage:security-review"
STAGE_MERGING = "stage:merging"
STAGE_ACCEPTANCE = "stage:acceptance"
STAGE_INVESTIGATING = "stage:investigating"
STAGE_CONSOLIDATING = "stage:consolidating"

STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_CLOSED = "closed"
STATUS_BLOCKED = "blocked"

CONFIG_DIR = Path(".debussy")
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "max_total_agents": 8,
    "use_tmux_windows": False,
}

STAGE_TO_ROLE = {
    STAGE_ACCEPTANCE: "tester",
    STAGE_MERGING: "integrator",
    STAGE_SECURITY_REVIEW: "security-reviewer",
    STAGE_REVIEWING: "reviewer",
    STAGE_CONSOLIDATING: "investigator",
    STAGE_INVESTIGATING: "investigator",
    STAGE_DEVELOPMENT: "developer",
}

NEXT_STAGE = {
    STAGE_DEVELOPMENT: STAGE_REVIEWING,
    STAGE_REVIEWING: STAGE_MERGING,
    STAGE_SECURITY_REVIEW: STAGE_MERGING,
    STAGE_MERGING: None,
    STAGE_ACCEPTANCE: None,
    STAGE_INVESTIGATING: None,
    STAGE_CONSOLIDATING: None,
}

SECURITY_NEXT_STAGE = {
    STAGE_REVIEWING: STAGE_SECURITY_REVIEW,
}

STAGE_SHORT = {
    STAGE_DEVELOPMENT: "dev",
    STAGE_REVIEWING: "rev",
    STAGE_SECURITY_REVIEW: "sec",
    STAGE_MERGING: "merge",
    STAGE_ACCEPTANCE: "accept",
    STAGE_INVESTIGATING: "inv",
    STAGE_CONSOLIDATING: "cons",
}


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
    except OSError:
        os.unlink(tmp)
        raise


def get_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return {**DEFAULTS, **cfg}
    except (OSError, ValueError):
        return DEFAULTS.copy()


def _read_config_file() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


KNOWN_KEYS = {"max_total_agents", "use_tmux_windows", "base_branch", "paused", "agent_timeout"}


def set_config(key: str, value):
    CONFIG_DIR.mkdir(exist_ok=True)
    cfg = _read_config_file()
    cfg[key] = value
    atomic_write(CONFIG_FILE, json.dumps(cfg, indent=2))


def clean_config():
    cfg = _read_config_file()
    unknown = [k for k in cfg if k not in KNOWN_KEYS]
    if not unknown:
        return
    for k in unknown:
        del cfg[k]
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
