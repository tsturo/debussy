# Watcher Remote Branch Gate

## Problem

~70% of developer tasks fail because the developer commits in a worktree but doesn't push to `origin`. The watcher advances the task to review, the reviewer finds no remote branch, and rejects. After 3 rejections the task blocks.

## Root Cause

Two gaps in the pipeline:

1. **`transitions.py` `_handle_agent_success()`** checks `_branch_has_commits()` using `origin/feature/{task_id}` — a local tracking ref that is stale because no `git fetch` runs first. The developer works in a worktree; the watcher runs in the main repo with outdated refs.

2. **`developer.md`** has push instructions but no post-push verification. If push silently fails (wrong remote config, auth issue), the agent proceeds to `takt release` anyway.

## Approach

Minimal fix at the two failure points. No changes to spawner.py (reviewer has no worktree; security-reviewer/integrator worktree creation already fails safely if fetch fails) or reviewer.md (already has early-exit branch check).

## Changes

### 1. `src/debussy/transitions.py`

Add `_remote_branch_exists()` using `git ls-remote` (queries the actual remote, not local refs). Returns `True` if the branch exists, `False` if it doesn't, `None` if the remote is unreachable (so we don't burn retry budget on network blips):

```python
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
```

Modify the `STAGE_DEVELOPMENT` block in `_handle_agent_success()`. On network failure (`None`), skip the check and let the existing `_branch_has_commits` path handle it (which already fail-opens on errors):

```python
if stage == STAGE_DEVELOPMENT:
    subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
    remote_exists = _remote_branch_exists(task_id)
    if remote_exists is False:
        return _handle_empty_branch(watcher, agent, task, db)
    base = get_config().get("base_branch", "master")
    if not _branch_has_commits(task_id, base):
        return _handle_empty_branch(watcher, agent, task, db)
```

The fetch refreshes local tracking refs so `_branch_has_commits()` works correctly. The `ls-remote` catches the case where the branch was never pushed. Network failures return `None` and are skipped — we don't burn retry budget on transient issues.

### 2. `src/debussy/prompts/developer.md`

Add a `git ls-remote` verification step between push and release. Renumber steps 11-12 to 12-13:

```
10. Commit changes, then push: `git push -u origin feature/<TASK_ID>`.
    Verify the push succeeded (exit code 0). If push fails, retry once after
    `git pull --rebase origin feature/<TASK_ID>`. If still failing, block the task.
11. VERIFY PUSH: run `git ls-remote --heads origin feature/<TASK_ID>` — if output
    is empty, the push did not land. Retry push once. If still empty, block the task
    with reason "push not landing on remote".
12. takt release <TASK_ID>
13. Exit
```

## What This Does NOT Change

- **`spawner.py`**: The fetch at line 49 already runs. If it fails, worktree creation fails, which aborts the spawn. No additional handling needed.
- **`reviewer.md`**: Already has `git rev-parse --verify origin/feature/<TASK_ID>` early exit at line 12.
- **`worktree.py`**: Not involved in this bug.

## Testing

- Unit test `_remote_branch_exists()`: branch exists (True), branch missing (False), network failure (None).
- Unit test `_handle_agent_success()` development path: remote missing triggers `_handle_empty_branch`, network failure skips the check and falls through to `_branch_has_commits`.
