#!/usr/bin/env python3
import json
import os
import subprocess
import sys

ALLOWED_LABELS = {
    "developer": set(),
    "reviewer": {"rejected"},
    "tester": {"rejected"},
    "investigator": set(),
    "integrator": {"rejected"},
}

ALLOWED_STATUSES = {
    "developer": {"in_progress", "open", "blocked"},
    "reviewer": {"in_progress", "open"},
    "tester": {"in_progress", "open", "closed"},
    "investigator": {"in_progress", "closed", "blocked"},
    "integrator": {"in_progress", "open"},
}


def _extract_flag_values(words, flag):
    values = []
    for i, word in enumerate(words):
        if word == flag and i + 1 < len(words):
            values.append(words[i + 1])
    return values


def _extract_bead_id(command):
    words = command.split()
    for i, word in enumerate(words):
        if word in ("update", "show") and i + 1 < len(words):
            return words[i + 1]
    return None


def _get_existing_stages(bead_id):
    try:
        result = subprocess.run(
            ["bd", "show", bead_id, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        bead = data[0] if isinstance(data, list) and data else data
        return [l for l in bead.get("labels", []) if l.startswith("stage:")]
    except Exception:
        return []


def _validate_singleton_stage(command):
    words = command.split()
    adding = [l for l in _extract_flag_values(words, "--add-label") if l.startswith("stage:")]
    if not adding:
        return

    removing = set(_extract_flag_values(words, "--remove-label"))
    bead_id = _extract_bead_id(command)
    if not bead_id:
        return

    existing = _get_existing_stages(bead_id)
    remaining = [s for s in existing if s not in removing]

    if remaining:
        print(f"Cannot add {adding[0]}: bead {bead_id} already has {remaining[0]}. Remove it first.", file=sys.stderr)
        sys.exit(2)


def _validate_labels(command, role):
    words = command.split()
    for label in _extract_flag_values(words, "--add-label"):
        if label.startswith("stage:"):
            print(f"Agents cannot set stage labels. The watcher manages stage transitions.", file=sys.stderr)
            sys.exit(2)
        allowed = ALLOWED_LABELS.get(role, set())
        if label not in allowed:
            print(f"Invalid: {role} cannot add label '{label}'", file=sys.stderr)
            sys.exit(2)
    for label in _extract_flag_values(words, "--remove-label"):
        if label.startswith("stage:"):
            print(f"Agents cannot remove stage labels. The watcher manages stage transitions.", file=sys.stderr)
            sys.exit(2)


def _validate_statuses(command, role):
    words = command.split()
    allowed = ALLOWED_STATUSES.get(role)
    if not allowed:
        return
    for status in _extract_flag_values(words, "--status"):
        if status not in allowed:
            print(f"Invalid: {role} cannot set status to '{status}'. Allowed: {' '.join(sorted(allowed))}", file=sys.stderr)
            sys.exit(2)


def main():
    hook_input = json.load(sys.stdin)
    command = hook_input.get("tool_input", {}).get("command", "")

    if "bd update" in command:
        _validate_singleton_stage(command)

    role = os.environ.get("DEBUSSY_ROLE")
    if not role:
        return

    if "bd close" in command:
        print("Use 'bd update <id> --status closed' instead of 'bd close'", file=sys.stderr)
        sys.exit(2)

    if "bd create" in command:
        _validate_labels(command, role)
        return

    if "bd update" in command:
        _validate_labels(command, role)
        _validate_statuses(command, role)
        return

if __name__ == "__main__":
    main()
