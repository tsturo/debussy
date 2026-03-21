import subprocess

from .config import get_config


NEEDS_FEATURE_BRANCH = {"reviewer", "security-reviewer"}

# Track already-warned tasks to avoid log spam (reset on watcher restart)
_warned_tasks: set[str] = set()


def check_base_branch() -> str | None:
    base = get_config().get("base_branch")
    if not base:
        return "base_branch not configured — run: debussy config base_branch <branch>"
    # Check local ref first (fast path)
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{base}"],
        capture_output=True, timeout=5,
    )
    if result.returncode == 0:
        return None
    # Local ref missing — try fetching before failing
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=15)
    except (subprocess.SubprocessError, OSError):
        pass
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{base}"],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return f"base_branch origin/{base} not found on remote"
    except (subprocess.SubprocessError, OSError) as e:
        return f"git check failed: {e}"
    return None


def check_remote_ref(ref: str) -> str | None:
    # Check local tracking ref first
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True, timeout=5,
    )
    if result.returncode == 0:
        return None
    # Not found locally — check remote directly (avoids stale local state)
    branch = ref.removeprefix("origin/")
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Exists on remote but not locally — fetch it
            subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=15)
            return None
    except (subprocess.SubprocessError, OSError):
        pass
    return f"ref {ref} not found"


def preflight_spawn(role: str, task_id: str) -> str | None:
    err = check_base_branch()
    if err:
        return err
    if role in NEEDS_FEATURE_BRANCH:
        err = check_remote_ref(f"origin/feature/{task_id}")
        if err:
            return err
    return None
