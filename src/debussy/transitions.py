"""Stage transition logic for the watcher pipeline."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .bead_client import get_bead_json
from .config import (
    NEXT_STAGE, SECURITY_NEXT_STAGE, STAGE_ACCEPTANCE, STAGE_DEVELOPMENT,
    STAGE_MERGING, STATUS_BLOCKED, STATUS_CLOSED, STATUS_IN_PROGRESS,
    STATUS_OPEN, get_config, log,
)
from .worktree import delete_branch

if TYPE_CHECKING:
    from .watcher import AgentInfo, Watcher

EVENTS_FILE = Path(".debussy/pipeline_events.jsonl")

MAX_RETRIES = 3
MAX_REJECTIONS = 5
REJECTION_COOLDOWN = 60


def record_event(bead_id: str, event: str, **kwargs: object) -> None:
    entry = {"ts": time.time(), "bead": bead_id, "event": event, **kwargs}
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _branch_has_commits(bead_id: str, base: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base}..origin/feature/{bead_id}"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and int(result.stdout.strip()) > 0
    except (subprocess.SubprocessError, OSError, ValueError):
        return True


@dataclass
class TransitionResult:
    status: str | None = None
    add_labels: list[str] = field(default_factory=list)
    remove_labels: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.status is not None or bool(self.add_labels) or bool(self.remove_labels)


def _is_terminal_stage(stage: str) -> bool:
    return NEXT_STAGE.get(stage) is None


def _verify_merge_landed(bead_id: str) -> bool:
    base = get_config().get("base_branch", "master")
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        return True
    try:
        ref_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/feature/{bead_id}"],
            capture_output=True, timeout=5,
        )
        if ref_check.returncode != 0:
            return True
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor",
             f"origin/feature/{bead_id}", f"origin/{base}"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return True


def _handle_in_progress_reset(agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    log(f"Agent left {agent.bead} as in_progress, resetting to open for retry", "⚠️")
    return TransitionResult(
        status=STATUS_OPEN,
        remove_labels=stage_labels[1:],
    )


def _handle_external_removal(agent: AgentInfo, has_rejected: bool) -> TransitionResult:
    log(f"Stage removed externally for {agent.bead}, skipping transition", "⏭️")
    result = TransitionResult()
    if has_rejected:
        result.remove_labels = ["rejected"]
    return result


def _handle_acceptance_rejection(agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    log(f"Acceptance failed {agent.bead}: blocked for conductor to create fix tasks", "🚫")
    record_event(agent.bead, "reject", **{"from": agent.spawned_stage, "to": STATUS_BLOCKED})
    extra_stages = [l for l in stage_labels if l != STAGE_ACCEPTANCE]
    return TransitionResult(
        status=STATUS_BLOCKED,
        remove_labels=["rejected"] + extra_stages,
    )


def _handle_rejection(watcher: Watcher, agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    watcher.rejections[agent.bead] = watcher.rejections.get(agent.bead, 0) + 1
    count = watcher.rejections[agent.bead]
    result = TransitionResult(remove_labels=stage_labels + ["rejected"])

    if count >= MAX_REJECTIONS:
        result.status = STATUS_BLOCKED
        log(f"Blocked {agent.bead}: rejected {count} times, needs conductor", "🚫")
        record_event(agent.bead, "loop_blocked", stage=agent.spawned_stage, rejections=count)
        try:
            subprocess.run(
                ["bd", "comment", agent.bead, f"Blocked after {count} rejection loops — needs conductor intervention"],
                capture_output=True, timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            pass
    else:
        result.add_labels = [STAGE_DEVELOPMENT]
        watcher.cooldowns[agent.bead] = time.time()
        log(f"Rejected {agent.bead} ({count}/{MAX_REJECTIONS}): {agent.spawned_stage} → {STAGE_DEVELOPMENT} (cooldown {REJECTION_COOLDOWN}s)", "↩️")

    watcher._save_rejections()
    record_event(agent.bead, "reject", **{"from": agent.spawned_stage, "to": STAGE_DEVELOPMENT})
    return result


def _handle_premature_close(watcher: Watcher, agent: AgentInfo, labels: list[str], stage_labels: list[str]) -> TransitionResult:
    log(f"Agent closed {agent.bead} at non-terminal {agent.spawned_stage}, reopening and advancing", "⚠️")
    record_event(agent.bead, "premature_close", stage=agent.spawned_stage)
    result = _handle_advance(watcher, agent, labels, stage_labels)
    if result.status is None:
        result.status = STATUS_OPEN
    return result


def _handle_unverified_merge(agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    log(f"Merge not verified on base branch for {agent.bead}, retrying merge", "⚠️")
    record_event(agent.bead, "unverified_merge", stage=agent.spawned_stage)
    return TransitionResult(
        status=STATUS_OPEN,
        remove_labels=stage_labels,
        add_labels=[STAGE_MERGING],
    )


def _handle_closed(watcher: Watcher, agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    watcher.rejections.pop(agent.bead, None)
    watcher._save_rejections()
    delete_branch(f"feature/{agent.bead}")
    log(f"Closed {agent.bead}: {agent.spawned_stage} complete", "✅")
    record_event(agent.bead, "close", stage=agent.spawned_stage)
    return TransitionResult(remove_labels=stage_labels)


def _handle_blocked(agent: AgentInfo, stage_labels: list[str]) -> TransitionResult:
    log(f"Blocked {agent.bead}: parked for conductor", "⊘")
    record_event(agent.bead, "block", stage=agent.spawned_stage)
    return TransitionResult(remove_labels=stage_labels)


def _compute_next_stage(agent: AgentInfo, labels: list[str]) -> str | None:
    if "security" in labels and agent.spawned_stage in SECURITY_NEXT_STAGE:
        return SECURITY_NEXT_STAGE[agent.spawned_stage]
    return NEXT_STAGE.get(agent.spawned_stage)


def _handle_empty_branch(watcher: Watcher, agent: AgentInfo) -> TransitionResult:
    watcher.empty_branch_retries[agent.bead] = watcher.empty_branch_retries.get(agent.bead, 0) + 1
    count = watcher.empty_branch_retries[agent.bead]

    if count >= MAX_RETRIES:
        log(f"Blocked {agent.bead}: empty branch after {count} attempts, needs conductor", "🚫")
        record_event(agent.bead, "empty_branch_blocked", stage=agent.spawned_stage, retries=count)
        try:
            subprocess.run(
                ["bd", "comment", agent.bead, f"Blocked after {count} empty-branch retries — needs conductor intervention"],
                capture_output=True, timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            pass
        return TransitionResult(status=STATUS_BLOCKED)

    log(f"No commits on feature/{agent.bead} — retry {count}/{MAX_RETRIES}", "⚠️")
    record_event(agent.bead, "empty_branch", stage=agent.spawned_stage, retry=count)
    return TransitionResult(add_labels=[STAGE_DEVELOPMENT])


def _handle_advance(watcher: Watcher, agent: AgentInfo, labels: list[str], stage_labels: list[str]) -> TransitionResult:
    next_stage = _compute_next_stage(agent, labels)
    if not next_stage:
        return TransitionResult(remove_labels=stage_labels)

    if agent.spawned_stage == STAGE_DEVELOPMENT:
        base = get_config().get("base_branch", "master")
        if not _branch_has_commits(agent.bead, base):
            result = _handle_empty_branch(watcher, agent)
            result.remove_labels = stage_labels
            return result

    watcher.empty_branch_retries.pop(agent.bead, None)
    log(f"Advancing {agent.bead}: {agent.spawned_stage} → {next_stage}", "⏩")
    record_event(agent.bead, "advance", **{"from": agent.spawned_stage, "to": next_stage})
    return TransitionResult(remove_labels=stage_labels, add_labels=[next_stage])


def _execute_transition(bead_id: str, result: TransitionResult) -> bool:
    if not result.has_changes:
        return True
    cmd = ["bd", "update", bead_id]
    if result.status:
        cmd.extend(["--status", result.status])
    for label in result.remove_labels:
        cmd.extend(["--remove-label", label])
    for label in result.add_labels:
        cmd.extend(["--add-label", label])
    try:
        run_result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if run_result.returncode != 0:
            log(f"Stage transition failed for {bead_id}: {run_result.stderr.strip()}", "⚠️")
            return False
    except (subprocess.SubprocessError, OSError) as e:
        log(f"Stage transition error for {bead_id}: {e}", "⚠️")
        return False
    verify_single_stage(bead_id)
    return True


def verify_single_stage(bead_id: str) -> None:
    bead = get_bead_json(bead_id)
    if not bead:
        return
    stages = [l for l in bead.get("labels", []) if l.startswith("stage:")]
    if len(stages) <= 1:
        return
    cmd = ["bd", "update", bead_id]
    for label in stages[1:]:
        cmd.extend(["--remove-label", label])
    try:
        subprocess.run(cmd, capture_output=True, timeout=5)
        log(f"Fixed {bead_id}: removed {len(stages)-1} extra stage label(s), kept {stages[0]}", "🔧")
    except (subprocess.SubprocessError, OSError):
        pass


def _dispatch_transition(watcher: Watcher, agent: AgentInfo, bead: dict) -> TransitionResult:
    labels = bead.get("labels", [])
    status = bead.get("status")
    has_rejected = "rejected" in labels
    stage_labels = [l for l in labels if l.startswith("stage:")]
    had_spawned_stage = agent.spawned_stage in stage_labels

    if status == STATUS_IN_PROGRESS:
        return _handle_in_progress_reset(agent, stage_labels)
    if not had_spawned_stage:
        return _handle_external_removal(agent, has_rejected)
    if has_rejected and agent.spawned_stage == STAGE_ACCEPTANCE:
        return _handle_acceptance_rejection(agent, stage_labels)
    if has_rejected:
        return _handle_rejection(watcher, agent, stage_labels)
    if status == STATUS_CLOSED:
        if not _is_terminal_stage(agent.spawned_stage):
            return _handle_premature_close(watcher, agent, labels, stage_labels)
        if agent.spawned_stage == STAGE_MERGING and not _verify_merge_landed(agent.bead):
            return _handle_unverified_merge(agent, stage_labels)
        return _handle_closed(watcher, agent, stage_labels)
    if status == STATUS_BLOCKED:
        return _handle_blocked(agent, stage_labels)
    if status == STATUS_OPEN:
        return _handle_advance(watcher, agent, labels, stage_labels)
    return TransitionResult(remove_labels=stage_labels)


def ensure_stage_transition(watcher: Watcher, agent: AgentInfo) -> bool:
    if not agent.spawned_stage:
        return True
    bead = get_bead_json(agent.bead)
    if not bead:
        log(f"Could not read bead {agent.bead}, skipping stage transition", "⚠️")
        return False
    result = _dispatch_transition(watcher, agent, bead)
    return _execute_transition(agent.bead, result)
