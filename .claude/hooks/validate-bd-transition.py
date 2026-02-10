#!/usr/bin/env python3
import json
import os
import sys

ALLOWED_TRANSITIONS = {
    "developer": {"reviewing", "open"},
    "reviewer": {"testing", "open"},
    "tester": {"merging", "done", "open"},
    "investigator": {"done", "open", "planning"},
    "integrator": {"done", "planning", "acceptance", "open"},
}

def _extract_status(words):
    for i, word in enumerate(words):
        if word == "--status" and i + 1 < len(words):
            return words[i + 1]
    return None


def _validate_create(command, role):
    words = command.split()
    target_status = _extract_status(words)
    if not target_status:
        return
    if target_status != "planning" and role != "investigator":
        print(f"Tasks must be created with --status planning (got '{target_status}')", file=sys.stderr)
        sys.exit(2)


def _validate_update(command, role):
    words = command.split()
    target_status = _extract_status(words)
    if not target_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(role)
    if allowed is None:
        return
    if target_status not in allowed:
        print(f"Invalid transition: {role} cannot set status to '{target_status}'. Allowed: {' '.join(sorted(allowed))}", file=sys.stderr)
        sys.exit(2)


def main():
    role = os.environ.get("DEBUSSY_ROLE")
    if not role:
        return

    hook_input = json.load(sys.stdin)
    command = hook_input.get("tool_input", {}).get("command", "")

    if "bd close" in command:
        print("Use 'bd update <id> --status <status>' instead of 'bd close'", file=sys.stderr)
        sys.exit(2)

    if "bd create" in command:
        _validate_create(command, role)
        return

    if "bd update" in command:
        _validate_update(command, role)
        return

if __name__ == "__main__":
    main()
