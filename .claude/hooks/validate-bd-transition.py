#!/usr/bin/env python3
import json
import os
import sys

ALLOWED_LABELS = {
    "developer": {"stage:reviewing"},
    "reviewer": {"stage:testing", "stage:development"},
    "tester": {"stage:merging", "stage:development"},
    "investigator": set(),
    "integrator": {"stage:acceptance", "stage:development"},
}

ALLOWED_STATUSES = {
    "developer": {"in_progress", "open"},
    "reviewer": {"in_progress", "open"},
    "tester": {"in_progress", "open", "closed"},
    "investigator": {"in_progress", "open", "closed"},
    "integrator": {"in_progress", "open"},
}


def _extract_flag_values(words, flag):
    values = []
    for i, word in enumerate(words):
        if word == flag and i + 1 < len(words):
            values.append(words[i + 1])
    return values


def _validate_create(command, role):
    words = command.split()
    labels = _extract_flag_values(words, "--add-label")
    for label in labels:
        if label.startswith("stage:"):
            print(f"Cannot create bead with stage label '{label}'", file=sys.stderr)
            sys.exit(2)


def _validate_update(command, role):
    words = command.split()

    statuses = _extract_flag_values(words, "--status")
    allowed_st = ALLOWED_STATUSES.get(role)
    if allowed_st:
        for status in statuses:
            if status not in allowed_st:
                print(f"Invalid: {role} cannot set status to '{status}'. Allowed: {' '.join(sorted(allowed_st))}", file=sys.stderr)
                sys.exit(2)

    labels = _extract_flag_values(words, "--add-label")
    allowed_lb = ALLOWED_LABELS.get(role)
    if allowed_lb is not None:
        for label in labels:
            if label.startswith("stage:") and label not in allowed_lb:
                print(f"Invalid: {role} cannot add label '{label}'. Allowed: {' '.join(sorted(allowed_lb))}", file=sys.stderr)
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
        _validate_create(command, role)
        return

    if "bd update" in command:
        _validate_update(command, role)
        return

if __name__ == "__main__":
    main()
