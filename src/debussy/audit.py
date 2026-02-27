"""Pipeline completeness audit for acceptance beads."""

import json
from pathlib import Path

from .bead_client import get_bead_json
from .config import (
    STAGE_DEVELOPMENT, STAGE_MERGING, STAGE_REVIEWING,
    STAGE_SECURITY_REVIEW,
)

EVENTS_FILE = Path(".debussy/pipeline_events.jsonl")

NORMAL_STAGES = {STAGE_DEVELOPMENT, STAGE_REVIEWING, STAGE_MERGING}
SECURITY_STAGES = NORMAL_STAGES | {STAGE_SECURITY_REVIEW}


def _load_all_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events = []
    with open(EVENTS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


def _partition_by_bead(events: list[dict]) -> dict[str, list[dict]]:
    by_bead: dict[str, list[dict]] = {}
    for e in events:
        by_bead.setdefault(e["bead"], []).append(e)
    return by_bead


def get_completed_stages(events: list[dict]) -> set[str]:
    completed: set[str] = set()
    for e in events:
        if e["event"] == "advance":
            completed.add(e["from"])
        elif e["event"] == "close":
            stage = e.get("stage")
            if stage:
                completed.add(stage)
    return completed


def expected_stages(has_security: bool) -> set[str]:
    return SECURITY_STAGES if has_security else NORMAL_STAGES


def audit_dep_bead(bead_id: str, events: list[dict]) -> tuple[bool, str]:
    bead = get_bead_json(bead_id)
    labels = bead.get("labels", []) if bead else []
    has_security = "security" in labels

    if not events:
        return False, f"{bead_id}: no pipeline events found"

    completed = get_completed_stages(events)
    required = expected_stages(has_security)
    missing = required - completed

    if missing:
        tag = " (security)" if has_security else ""
        names = ", ".join(sorted(s.replace("stage:", "") for s in missing))
        return False, f"{bead_id}{tag}: missing stages: {names}"

    return True, f"{bead_id}: ok"


def validate_bead_pipeline(bead_id: str) -> tuple[bool, str]:
    bead = get_bead_json(bead_id)
    labels = bead.get("labels", []) if bead else []
    has_security = "security" in labels

    all_events = _load_all_events()
    by_bead = _partition_by_bead(all_events)
    bead_events = by_bead.get(bead_id, [])

    if not bead_events:
        return False, f"{bead_id}: no pipeline events found"

    completed = get_completed_stages(bead_events)
    required = expected_stages(has_security) - {STAGE_MERGING}
    missing = required - completed

    if missing:
        tag = " (security)" if has_security else ""
        names = ", ".join(sorted(s.replace("stage:", "") for s in missing))
        return False, f"{bead_id}{tag}: missing stages: {names}"

    return True, f"{bead_id}: ok"


def audit_acceptance(bead_id: str) -> tuple[bool, str]:
    bead = get_bead_json(bead_id)
    if not bead:
        return False, f"Could not read acceptance bead {bead_id}"

    deps = bead.get("dependencies", [])
    if not deps:
        return True, "No dependencies to audit"

    all_events = _load_all_events()
    by_bead = _partition_by_bead(all_events)

    results = []
    all_passed = True
    for dep in deps:
        dep_id = dep.get("depends_on_id") or dep.get("id")
        if not dep_id:
            continue
        ok, detail = audit_dep_bead(dep_id, by_bead.get(dep_id, []))
        results.append(detail)
        if not ok:
            all_passed = False

    report = "\n".join(results)
    return all_passed, report
