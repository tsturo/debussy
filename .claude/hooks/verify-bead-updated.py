#!/usr/bin/env python3
import json
import os
import subprocess
import sys


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
            ["bd", "show", bead, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and data:
            current_status = data[0].get("status")
        else:
            return
    except Exception:
        return

    if current_status == "in_progress":
        json.dump({
            "decision": "block",
            "reason": f"You must update bead {bead} status before stopping. Current status is still 'in_progress'."
        }, sys.stdout)

if __name__ == "__main__":
    main()
