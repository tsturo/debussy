"""Pipeline scanning and bead lifecycle management."""

import json
import subprocess
import time

from .bead_client import get_bead_json, get_unresolved_deps
from .config import (
    STAGE_ACCEPTANCE, STAGE_DEVELOPMENT, STAGE_TO_ROLE,
    STATUS_BLOCKED, STATUS_CLOSED, STATUS_IN_PROGRESS, STATUS_OPEN,
    log,
)
from .spawner import MAX_TOTAL_SPAWNS, spawn_agent
from .transitions import MAX_RETRIES, REJECTION_COOLDOWN, record_event, verify_single_stage


def get_unmerged_dep_branches(bead: dict) -> list[str]:
    unmerged = []
    for dep in bead.get("dependencies", []):
        dep_id = dep.get("depends_on_id") or dep.get("id")
        if not dep_id:
            continue
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", f"feature/{dep_id}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                unmerged.append(dep_id)
        except (subprocess.SubprocessError, OSError):
            pass
    return unmerged


def _get_children(parent_id: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["bd", "list", "--parent", parent_id, "--all", "--limit", "0", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else []
    except (subprocess.SubprocessError, OSError, ValueError):
        return []


def reset_orphaned(watcher):
    try:
        result = subprocess.run(
            ["bd", "list", "--status", STATUS_IN_PROGRESS, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        beads = json.loads(result.stdout)
        if not isinstance(beads, list):
            return
    except (subprocess.SubprocessError, OSError, ValueError):
        return

    running_beads = {a.bead for a in watcher.running.values()}
    for bead in beads:
        bead_id = bead.get("id")
        if not bead_id or bead_id in running_beads:
            continue
        labels = bead.get("labels", [])
        stage_labels = [l for l in labels if l.startswith("stage:")]
        if not stage_labels:
            continue
        full_bead = get_bead_json(bead_id)
        real_labels = full_bead.get("labels", []) if full_bead else labels
        real_stages = [l for l in real_labels if l.startswith("stage:")]
        cmd = ["bd", "update", bead_id, "--status", STATUS_OPEN]
        for label in real_stages[1:]:
            cmd.extend(["--remove-label", label])
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            log(f"Reset orphaned {bead_id}: no agent running", "👻")
        except (subprocess.SubprocessError, OSError):
            pass


def release_ready(watcher):
    for status in (STATUS_BLOCKED, STATUS_OPEN):
        try:
            result = subprocess.run(
                ["bd", "list", "--status", status, "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            beads = json.loads(result.stdout)
            if not isinstance(beads, list):
                continue
        except (subprocess.SubprocessError, OSError, ValueError):
            continue

        for bead in beads:
            _try_release_bead(bead, status)


def _try_release_bead(bead, status):
    bead_id = bead.get("id")
    if not bead_id or bead.get("dependency_count", 0) == 0:
        return
    full_bead = get_bead_json(bead_id)
    if not full_bead or get_unresolved_deps(full_bead):
        return

    labels = full_bead.get("labels", [])
    has_stage = any(l.startswith("stage:") for l in labels)
    cmd = ["bd", "update", bead_id]

    if status == STATUS_BLOCKED and STAGE_ACCEPTANCE in labels:
        return
    if status == STATUS_BLOCKED:
        cmd.extend(["--status", STATUS_OPEN])
    if not has_stage:
        cmd.extend(["--add-label", STAGE_DEVELOPMENT])
    if len(cmd) <= 3:
        return

    try:
        subprocess.run(cmd, capture_output=True, timeout=5)
        if has_stage:
            log(f"Unblocked {bead_id}: deps resolved", "🔓")
            record_event(bead_id, "unblock")
        else:
            log(f"Released {bead_id}: deps resolved → {STAGE_DEVELOPMENT}", "🔓")
            record_event(bead_id, "release", stage=STAGE_DEVELOPMENT)
        verify_single_stage(bead_id)
    except (subprocess.SubprocessError, OSError):
        pass


def _should_skip_bead(watcher, bead_id, bead, role):
    if not bead_id:
        return "no id"
    if watcher.is_bead_running(bead_id):
        return "already running"
    cooldown_until = watcher.cooldowns.get(bead_id, 0)
    if cooldown_until and time.time() - cooldown_until < REJECTION_COOLDOWN:
        return "cooldown"
    if watcher.failures.get(bead_id, 0) >= MAX_RETRIES:
        _block_failed_bead(watcher, bead_id, "failures")
        return "max failures"
    if watcher.spawn_counts.get(bead_id, 0) >= MAX_TOTAL_SPAWNS:
        _block_failed_bead(watcher, bead_id, "total spawns")
        return "max spawns"
    if bead.get("status") == STATUS_BLOCKED:
        return "blocked"
    skip = _check_dependencies(watcher, bead_id, bead, role)
    if skip:
        return skip
    if role == "integrator" and watcher.has_running_role("integrator"):
        _queue_bead(watcher, bead_id, "waiting for integrator")
        return "integrator busy"
    if watcher.is_at_capacity():
        _queue_bead(watcher, bead_id, "waiting for agent slot")
        return "at capacity"
    return None


def _block_failed_bead(watcher, bead_id, reason="failures"):
    if bead_id in watcher.blocked_failures:
        return
    watcher.blocked_failures.add(bead_id)
    log(f"Blocked {bead_id}: max {reason}, needs conductor", "🚫")
    try:
        subprocess.run(
            ["bd", "update", bead_id, "--status", STATUS_BLOCKED],
            capture_output=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def _check_dependencies(watcher, bead_id, bead, role):
    if bead.get("dependency_count", 0) == 0:
        return None
    full_bead = get_bead_json(bead_id)
    if not full_bead or get_unresolved_deps(full_bead):
        return "unresolved deps"
    if role == "tester":
        unmerged = get_unmerged_dep_branches(full_bead)
        if unmerged:
            _queue_bead(watcher, bead_id, f"{len(unmerged)} dep branch(es) still unmerged on origin")
            return "unmerged deps"
    return None


def _queue_bead(watcher, bead_id, reason):
    if bead_id not in watcher.queued:
        log(f"Holding {bead_id}: {reason}", "⏳")
        watcher.queued.add(bead_id)


def _scan_stage(watcher, stage, role, spawn_budget: int) -> int:
    spawned = 0
    try:
        result = subprocess.run(
            ["bd", "list", "--status", STATUS_OPEN, "--label", stage, "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return 0
        beads = json.loads(result.stdout)
        if not isinstance(beads, list):
            return 0
    except subprocess.TimeoutExpired:
        log(f"Timeout checking {stage}", "⚠️")
        return 0
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        log(f"Error checking {stage}: {e}", "⚠️")
        return 0

    beads.sort(key=lambda b: b.get("issue_type") != "bug")
    for bead in beads:
        if spawned >= spawn_budget:
            break
        bead_id = bead.get("id")
        skip = _should_skip_bead(watcher, bead_id, bead, role)
        if skip:
            continue
        watcher.queued.discard(bead_id)
        if spawn_agent(watcher, role, bead_id, stage):
            spawned += 1
    return spawned


MAX_SPAWNS_PER_CYCLE = 2


def check_pipeline(watcher):
    budget = MAX_SPAWNS_PER_CYCLE
    for stage, role in STAGE_TO_ROLE.items():
        if budget <= 0:
            break
        budget -= _scan_stage(watcher, stage, role, budget)


def auto_close_parents(watcher):
    try:
        result = subprocess.run(
            ["bd", "list", "--status", STATUS_OPEN, "--no-parent", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        beads = json.loads(result.stdout)
        if not isinstance(beads, list):
            return
    except (subprocess.SubprocessError, OSError, ValueError):
        return

    for bead in beads:
        bead_id = bead.get("id")
        if not bead_id:
            continue
        labels = bead.get("labels", [])
        if any(l.startswith("stage:") for l in labels):
            continue
        children = _get_children(bead_id)
        if not children:
            continue
        if all(c.get("status") == STATUS_CLOSED for c in children):
            try:
                subprocess.run(
                    ["bd", "update", bead_id, "--status", STATUS_CLOSED],
                    capture_output=True, timeout=5,
                )
                log(f"Auto-closed parent {bead_id}: all children closed", "📦")
            except (subprocess.SubprocessError, OSError):
                pass
