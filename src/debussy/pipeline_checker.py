"""Pipeline scanning and task lifecycle management."""

import subprocess

from .config import (
    LABEL_PRIORITY, STAGE_ACCEPTANCE, STAGE_BACKLOG, STAGE_DEVELOPMENT,
    STAGE_TO_ROLE, STATUS_ACTIVE, STATUS_BLOCKED, STATUS_PENDING,
    POST_MERGE_STAGES,
    get_config, log,
)
from .spawner import MAX_TOTAL_SPAWNS, spawn_agent
from .takt import (
    add_comment, advance_task, block_task, get_db, get_task,
    get_unresolved_deps, list_tasks, release_task,
)
from .transitions import MAX_RETRIES


def get_unmerged_dep_branches(task: dict) -> list[str]:
    """Check which dependency branches haven't been merged on origin."""
    unmerged = []
    for dep_id in task.get("dependencies", []):
        with get_db() as db:
            dep_task = get_task(db, dep_id)
        if dep_task and dep_task["stage"] in POST_MERGE_STAGES:
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


def reset_orphaned(watcher):
    with get_db() as db:
        active_tasks = list_tasks(db, status=STATUS_ACTIVE)

    running_tasks = {a.task for a in watcher.running.values()}
    for task in active_tasks:
        task_id = task.get("id")
        if not task_id or task_id in running_tasks:
            continue
        # Only reset tasks that are in a stage the watcher manages
        if task.get("stage") not in STAGE_TO_ROLE:
            continue
        with get_db() as db:
            release_task(db, task_id)
        log(f"Reset orphaned {task_id}: no agent running", "👻")


def release_ready(watcher):
    with get_db() as db:
        blocked_tasks = list_tasks(db, status=STATUS_BLOCKED)
        backlog_tasks = list_tasks(db, stage=STAGE_BACKLOG, status=STATUS_PENDING)

    for task in blocked_tasks:
        _try_release_task(watcher, task, STATUS_BLOCKED)

    for task in backlog_tasks:
        _try_release_task(watcher, task, STATUS_PENDING)


def _try_release_task(watcher, task, status):
    task_id = task.get("id")
    if not task_id or not task.get("dependencies"):
        return

    with get_db() as db:
        unresolved = get_unresolved_deps(db, task_id)
    if unresolved:
        return

    stage = task.get("stage")

    if status == STATUS_BLOCKED and stage == STAGE_ACCEPTANCE:
        return
    if status == STATUS_BLOCKED and watcher.empty_branch_retries.get(task_id, 0) >= MAX_RETRIES:
        return

    with get_db() as db:
        if status == STATUS_BLOCKED:
            # Unblock: set back to pending
            release_task(db, task_id)
            log(f"Unblocked {task_id}: deps resolved", "🔓")
        elif stage == STAGE_BACKLOG:
            # Release from backlog to development
            advance_task(db, task_id, to_stage=STAGE_DEVELOPMENT)
            log(f"Released {task_id}: deps resolved → {STAGE_DEVELOPMENT}", "🔓")


def _should_skip_task(watcher, task_id, task, role):
    if not task_id:
        return "no id"
    if watcher.is_task_running(task_id):
        return "already running"
    if watcher.failures.get(task_id, 0) >= MAX_RETRIES:
        _block_failed_task(watcher, task_id, "failures")
        return "max failures"
    if watcher.spawn_counts.get(task_id, 0) >= MAX_TOTAL_SPAWNS:
        _block_failed_task(watcher, task_id, "total spawns")
        return "max spawns"
    if task.get("status") == STATUS_BLOCKED:
        return "blocked"
    skip = _check_dependencies(watcher, task_id, task, role)
    if skip:
        return skip
    max_for_role = get_config().get("max_role_agents", {}).get(role)
    if max_for_role and watcher.count_running_role(role) >= max_for_role:
        _queue_task(watcher, task_id, f"waiting for {role} slot")
        return f"{role} at cap"
    if watcher.is_at_capacity():
        _queue_task(watcher, task_id, "waiting for agent slot")
        return "at capacity"
    return None


def _block_failed_task(watcher, task_id, reason="failures"):
    if task_id in watcher.blocked_failures:
        return
    watcher.blocked_failures.add(task_id)
    log(f"Blocked {task_id}: max {reason}, needs conductor", "🚫")
    with get_db() as db:
        add_comment(db, task_id, "watcher", f"Blocked: max {reason} reached. Needs conductor intervention.")
        block_task(db, task_id)


def _check_dependencies(watcher, task_id, task, role):
    if not task.get("dependencies"):
        return None
    with get_db() as db:
        unresolved = get_unresolved_deps(db, task_id)
    if unresolved:
        return "unresolved deps"
    if role == "tester":
        unmerged = get_unmerged_dep_branches(task)
        if unmerged:
            _queue_task(watcher, task_id, f"{len(unmerged)} dep branch(es) still unmerged on origin")
            return "unmerged deps"
    return None


def _queue_task(watcher, task_id, reason):
    if task_id not in watcher.queued:
        log(f"Holding {task_id}: {reason}", "⏳")
        watcher.queued.add(task_id)


def _scan_stage(watcher, stage, role, spawn_budget: int) -> int:
    spawned = 0
    with get_db() as db:
        tasks = list_tasks(db, stage=stage, status=STATUS_PENDING)

    tasks.sort(key=lambda t: (
        LABEL_PRIORITY not in t.get("tags", []),
        "bug" not in t.get("tags", []),
    ))
    for task in tasks:
        if spawned >= spawn_budget:
            break
        task_id = task.get("id")
        skip = _should_skip_task(watcher, task_id, task, role)
        if skip:
            continue
        watcher.queued.discard(task_id)
        if spawn_agent(watcher, role, task_id, stage, labels=task.get("tags")):
            spawned += 1
    return spawned


MAX_SPAWNS_PER_CYCLE = 2


def check_pipeline(watcher):
    budget = MAX_SPAWNS_PER_CYCLE
    for stage, role in STAGE_TO_ROLE.items():
        if budget <= 0:
            break
        budget -= _scan_stage(watcher, stage, role, budget)
