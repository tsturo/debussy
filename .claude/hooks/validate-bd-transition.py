#!/usr/bin/env python3
import json
import os
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
    role = os.environ.get("DEBUSSY_ROLE")
    if not role:
        return

    hook_input = json.load(sys.stdin)
    command = hook_input.get("tool_input", {}).get("command", "")

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
