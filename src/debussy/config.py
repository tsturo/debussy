"""Configuration for Debussy."""

import json
from pathlib import Path

POLL_INTERVAL = 5
YOLO_MODE = True
SESSION_NAME = "debussy"
SINGLETON_ROLES = ["integrator"]

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


def get_config():
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
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_base_branch() -> str | None:
    cfg = get_config()
    return cfg.get("base_branch")


def get_max_for_role(role: str) -> int:
    if role in SINGLETON_ROLES:
        return 1
    cfg = get_config()
    return cfg.get(f"max_{role}s", 3)
