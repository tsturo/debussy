"""Thin wrapper around the bd CLI for cross-module bead operations."""

from __future__ import annotations

import json
import subprocess

from .config import STATUS_BLOCKED, STATUS_CLOSED, STATUS_IN_PROGRESS, STATUS_OPEN


def get_bead_json(bead_id: str) -> dict | None:
    try:
        result = subprocess.run(
            ["bd", "show", bead_id, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and data:
            return data[0]
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return None


def get_bead_status(bead_id: str) -> str | None:
    bead = get_bead_json(bead_id)
    return bead.get("status") if bead else None


def get_all_beads() -> list[dict]:
    beads = {}
    for status in (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_CLOSED, STATUS_BLOCKED):
        try:
            result = subprocess.run(
                ["bd", "list", "--status", status, "--limit", "0", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout)
            if isinstance(data, list):
                for bead in data:
                    bead_id = bead.get("id")
                    if bead_id:
                        beads[bead_id] = bead
        except (subprocess.SubprocessError, OSError, ValueError):
            continue
    return list(beads.values())


def update_bead(bead_id: str, status: str | None = None,
                add_labels: list[str] | None = None,
                remove_labels: list[str] | None = None) -> subprocess.CompletedProcess[str] | None:
    cmd = ["bd", "update", bead_id]
    if status:
        cmd.extend(["--status", status])
    for label in (add_labels or []):
        cmd.extend(["--add-label", label])
    for label in (remove_labels or []):
        cmd.extend(["--remove-label", label])
    if len(cmd) <= 3:
        return None
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5)


def comment_bead(bead_id: str, text: str) -> None:
    subprocess.run(
        ["bd", "comment", bead_id, text],
        capture_output=True, timeout=5,
    )


def get_unresolved_deps(bead: dict) -> list[str]:
    unresolved = []
    for dep in bead.get("dependencies", []):
        dep_id = dep.get("depends_on_id") or dep.get("id")
        if not dep_id:
            continue
        status = dep.get("status") or get_bead_status(dep_id)
        if status != STATUS_CLOSED:
            unresolved.append(dep_id)
    return unresolved
