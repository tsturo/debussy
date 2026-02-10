#!/usr/bin/env python3
import json
import os
import sys

ALLOWED_TRANSITIONS = {
    "developer": {"reviewing", "open"},
    "reviewer": {"testing", "open"},
    "tester": {"merging", "done", "open"},
    "investigator": {"done", "open"},
    "integrator": {"done", "planning", "acceptance", "open"},
}

def main():
    role = os.environ.get("DEBUSSY_ROLE")
    if not role:
        return

    hook_input = json.load(sys.stdin)
    command = hook_input.get("tool_input", {}).get("command", "")

    if "bd close" not in command and "bd update" not in command:
        return

    if "bd close" in command:
        print("Use 'bd update <id> --status <status>' instead of 'bd close'", file=sys.stderr)
        sys.exit(2)

    words = command.split()
    target_status = None
    for i, word in enumerate(words):
        if word == "--status" and i + 1 < len(words):
            target_status = words[i + 1]
            break

    if not target_status:
        return

    allowed = ALLOWED_TRANSITIONS.get(role)
    if allowed is None:
        return

    if target_status not in allowed:
        print(f"Invalid transition: {role} cannot set status to '{target_status}'. Allowed: {' '.join(sorted(allowed))}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
