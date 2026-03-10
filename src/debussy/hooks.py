"""Manage Claude Code hooks in target projects."""

import json
from pathlib import Path

SETTINGS_FILE = Path(".claude/settings.json")

DEBUSSY_HOOKS = {
    "PreCompact": [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": "echo 'URGENT: Context compaction is about to happen. You MUST update .debussy/conductor-context.md with your current state RIGHT NOW before context is lost. Write the file, then compaction will proceed.'"
                }
            ]
        }
    ]
}


def install_hooks():
    settings = _read_settings()
    hooks = settings.setdefault("hooks", {})
    for event, entries in DEBUSSY_HOOKS.items():
        existing = hooks.get(event, [])
        for entry in entries:
            if not _has_matching_hook(existing, entry):
                existing.append(entry)
        hooks[event] = existing
    _write_settings(settings)


def uninstall_hooks():
    settings = _read_settings()
    hooks = settings.get("hooks", {})
    for event, entries in DEBUSSY_HOOKS.items():
        existing = hooks.get(event, [])
        hooks[event] = [
            e for e in existing if not _has_matching_hook([e], entries[0])
        ]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    _write_settings(settings)


def _has_matching_hook(existing: list, target: dict) -> bool:
    target_cmd = target.get("hooks", [{}])[0].get("command", "")
    for entry in existing:
        for hook in entry.get("hooks", []):
            if hook.get("command", "") == target_cmd:
                return True
    return False


def _read_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _write_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n")
