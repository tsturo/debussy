#!/usr/bin/env python3
import json
import os
import subprocess
import sys

BAD_STATUSES = {
    "developer": {"open"},
    "reviewer": {"reviewing"},
    "tester": {"testing", "acceptance"},
    "investigator": {"investigating"},
    "integrator": {"consolidating", "merging"},
}

def main():
    role = os.environ.get("DEBUSSY_ROLE")
    bead = os.environ.get("DEBUSSY_BEAD")
    if not role or not bead:
        return

    hook_input = json.load(sys.stdin)
    if hook_input.get("stop_hook_active"):
        return

    try:
        result = subprocess.run(
            ["bd", "show", bead],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        return

    if not result.stdout:
        return

    current_status = None
    for line in result.stdout.splitlines():
        if "status" in line.lower():
            current_status = line.split()[-1]
            break

    if not current_status:
        return

    bad = BAD_STATUSES.get(role)
    if bad is None:
        return

    if current_status in bad:
        json.dump({
            "decision": "block",
            "reason": f"You must update bead {bead} status before stopping. Current status is still '{current_status}'."
        }, sys.stdout)

if __name__ == "__main__":
    main()
