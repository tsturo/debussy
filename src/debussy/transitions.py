"""Stage transition logic for the watcher pipeline."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from .config import (
    STAGE_ACCEPTANCE, STAGE_DEVELOPMENT, STAGE_MERGING,
    STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    STAGE_REQUIRED_TAGS,
    get_config, log,
)
from .takt import (
    get_db, get_task, advance_task, release_task,
    block_task, add_comment, update_task,
)
from .takt.log import add_log
from .config import NEXT_STAGE, SECURITY_NEXT_STAGE
from .worktree import delete_branch

if TYPE_CHECKING:
    from .agent import AgentInfo
    from .watcher import Watcher

MAX_RETRIES = 3


def _remote_branch_exists(task_id: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", f"feature/{task_id}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        return None


def _branch_has_commits(task_id: str, base: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base}..origin/feature/{task_id}"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and int(result.stdout.strip()) > 0
    except (subprocess.SubprocessError, OSError, ValueError):
        log(f"Git error checking commits for feature/{task_id}, treating as no commits", "⚠️")
        return False


# Stages where agent completion means "task is done" (watcher moves to done)
_TERMINAL_STAGES = {STAGE_ACCEPTANCE}


def _is_terminal_stage(stage: str) -> bool:
    return stage in _TERMINAL_STAGES


def _verify_merge_landed(task_id: str) -> bool:
    base = get_config().get("base_branch", "master")
    log(f"Fetching origin to verify merge for {task_id}", "🔄")
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        log(f"Git fetch failed/timed out for {task_id}, cannot verify merge", "⚠️")
        return False
    try:
        ref_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/feature/{task_id}"],
            capture_output=True, timeout=5,
        )
        if ref_check.returncode != 0:
            log(f"origin/feature/{task_id} does not exist on remote", "⚠️")
            return False
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor",
             f"origin/feature/{task_id}", f"origin/{base}"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        log(f"Git error verifying merge for {task_id}, treating as unverified", "⚠️")
        return False


def _compute_next_stage(spawned_stage: str, tags: list[str]) -> str | None:
    """Compute the next stage, skipping tag-gated stages the task doesn't qualify for."""
    if _is_terminal_stage(spawned_stage):
        return None
    if "security" in tags and spawned_stage in SECURITY_NEXT_STAGE:
        return SECURITY_NEXT_STAGE[spawned_stage]
    next_s = NEXT_STAGE.get(spawned_stage)
    if next_s is None:
        return None
    # Skip stages the task doesn't have the required tag for
    while next_s in STAGE_REQUIRED_TAGS:
        required_tag = STAGE_REQUIRED_TAGS[next_s]
        if required_tag in tags:
            return next_s
        next_s = NEXT_STAGE.get(next_s)
        if next_s is None:
            return None
    return next_s


def _dispatch_transition(watcher: Watcher, agent: AgentInfo, task: dict, db) -> bool:
    """Dispatch the appropriate transition based on task state after agent finishes."""
    status = task["status"]
    stage = task["stage"]
    tags = task.get("tags", [])
    task_id = agent.task

    # Agent left task as active — reset to pending for retry
    if status == STATUS_ACTIVE:
        log(f"Agent left {task_id} as active, resetting to pending for retry", "⚠️")
        release_task(db, task_id)
        return True

    # Stage was changed externally (not the one we spawned for)
    if stage != agent.spawned_stage:
        log(f"Stage changed externally for {task_id}, skipping transition", "⏭️")
        return True

    # Blocked — park for conductor
    if status == STATUS_BLOCKED:
        log(f"Blocked {task_id}: parked for conductor", "⊘")
        add_log(db, task_id, "transition", "watcher", f"blocked at {stage}")
        return True

    # Pending — agent finished work, determine next action
    if status == STATUS_PENDING:
        return _handle_agent_success(watcher, agent, task, db)

    return True


def _handle_agent_success(watcher: Watcher, agent: AgentInfo, task: dict, db) -> bool:
    """Handle the case where an agent finished and set status=pending."""
    task_id = agent.task
    stage = task["stage"]
    tags = task.get("tags", [])

    # Terminal stages: task is done
    if _is_terminal_stage(stage):
        update_task(db, task_id, stage="done")
        log(f"Closed {task_id}: {stage} complete", "✅")
        add_log(db, task_id, "transition", "watcher", f"{stage} -> done")
        return True

    # Merging: verify merge landed, delete branch, then advance to post-merge
    if stage == STAGE_MERGING:
        if not _verify_merge_landed(task_id):
            log(f"Merge not verified on base branch for {task_id}, retrying merge", "⚠️")
            add_log(db, task_id, "transition", "watcher", "unverified merge, retrying")
            return True
        delete_branch(f"feature/{task_id}")

    if stage == STAGE_DEVELOPMENT:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
        remote_exists = _remote_branch_exists(task_id)
        if remote_exists is False:
            return _handle_empty_branch(watcher, agent, task, db)
        base = get_config().get("base_branch", "master")
        if not _branch_has_commits(task_id, base):
            return _handle_empty_branch(watcher, agent, task, db)

    # Advance to next stage
    watcher.empty_branch_retries.pop(task_id, None)
    next_stage = _compute_next_stage(stage, tags)
    if next_stage:
        advance_task(db, task_id, to_stage=next_stage)
        log(f"Advancing {task_id}: {stage} → {next_stage}", "⏩")
    else:
        update_task(db, task_id, stage="done")
        log(f"Closed {task_id}: no next stage from {stage}", "✅")
    return True


def _handle_empty_branch(watcher: Watcher, agent: AgentInfo, task: dict, db) -> bool:
    """Handle developer completing without commits on the feature branch."""
    task_id = agent.task
    watcher.empty_branch_retries[task_id] = watcher.empty_branch_retries.get(task_id, 0) + 1
    count = watcher.empty_branch_retries[task_id]

    if count >= MAX_RETRIES:
        log(f"Blocked {task_id}: empty branch after {count} attempts, needs conductor", "🚫")
        block_task(db, task_id)
        add_comment(db, task_id, "watcher",
                    f"Blocked after {count} empty-branch retries — needs conductor intervention")
        return True

    log(f"No commits on feature/{task_id} — retry {count}/{MAX_RETRIES}", "⚠️")
    add_log(db, task_id, "transition", "watcher", f"empty branch retry {count}/{MAX_RETRIES}")
    # Keep at development stage for another attempt
    release_task(db, task_id)
    return True


def ensure_stage_transition(watcher: Watcher, agent: AgentInfo) -> bool:
    """Main entry point: read task state and dispatch appropriate transition."""
    if not agent.spawned_stage:
        return True

    with get_db() as db:
        task = get_task(db, agent.task)
        if not task:
            log(f"Could not read task {agent.task}, skipping stage transition", "⚠️")
            return False
        return _dispatch_transition(watcher, agent, task, db)
