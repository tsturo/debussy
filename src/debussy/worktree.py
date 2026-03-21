"""Git worktree lifecycle management for parallel agent isolation."""

import shutil
import subprocess
from pathlib import Path

from .agent import repo_root
from .config import STAGE_DONE, get_config, log
from .takt import get_db, list_tasks

WORKTREES_DIR = ".debussy-worktrees"


def _remove_symlinks(worktree_path: Path):
    for name in (".takt", ".debussy"):
        link = worktree_path / name
        if link.is_symlink():
            link.unlink()


def _worktree_path(agent_name: str) -> Path:
    return repo_root() / WORKTREES_DIR / agent_name


def _symlink_dirs(worktree: Path, repo: Path):
    wt_dir = repo / WORKTREES_DIR
    if not str(worktree.resolve()).startswith(str(wt_dir.resolve()) + "/"):
        raise RuntimeError(
            f"Refusing to symlink into {worktree} — not inside {wt_dir}"
        )
    for name in (".takt", ".debussy"):
        src = repo / name
        dest = worktree / name
        if src.exists() and not dest.exists():
            dest.symlink_to(src.resolve())


def _branch_exists(branch: str) -> bool:
    for ref in (branch, f"refs/remotes/origin/{branch}"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return True
    return False


def _remove_worktree_for_branch(branch: str):
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=10,
    )
    wt_dir = repo_root() / WORKTREES_DIR
    current_path = None
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            current_path = line.split(" ", 1)[1]
        elif line.startswith("branch ") and current_path:
            wt_branch = line.split(" ", 1)[1].replace("refs/heads/", "")
            if wt_branch == branch and str(wt_dir) in current_path:
                agent_name = Path(current_path).name
                remove_worktree(agent_name)
                log(f"Removed stale worktree {agent_name} holding branch {branch}", "🧹")
            current_path = None
        elif not line.strip():
            current_path = None


def create_worktree(agent_name: str, branch: str, start_point: str | None = None, new_branch: bool = False, detach: bool = False) -> Path:
    wt_path = _worktree_path(agent_name)
    repo = repo_root()

    subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)

    if wt_path.exists():
        remove_worktree(agent_name)

    if not detach:
        _remove_worktree_for_branch(branch)

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    if detach:
        cmd = ["git", "worktree", "add", "--detach", str(wt_path), branch]
    elif new_branch:
        cmd = ["git", "worktree", "add", "-b", branch, str(wt_path)]
        if start_point:
            cmd.append(start_point)
    else:
        cmd = ["git", "worktree", "add", str(wt_path), branch]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 and new_branch and "already exists" in result.stderr:
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
        cmd = ["git", "worktree", "add", str(wt_path), branch]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 and new_branch:
        subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
        if _branch_exists(branch):
            subprocess.run(["git", "branch", "-D", branch], capture_output=True, timeout=10)
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
        cmd = ["git", "worktree", "add", "-b", branch, str(wt_path)]
        if start_point:
            cmd.append(start_point)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    _symlink_dirs(wt_path, repo)
    return wt_path


def remove_worktree(agent_name: str):
    wt_path = _worktree_path(agent_name)
    if not wt_path.exists():
        return

    _remove_symlinks(wt_path)

    result = subprocess.run(
        ["git", "worktree", "remove", "--force", str(wt_path)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0 and wt_path.exists():
        shutil.rmtree(wt_path, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)


def _get_done_task_ids() -> set[str]:
    try:
        with get_db() as db:
            tasks = list_tasks(db, stage=STAGE_DONE)
        return {t["id"] for t in tasks}
    except Exception:
        return set()


def _worktree_branches() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        branches = set()
        for line in result.stdout.split("\n"):
            if line.startswith("branch "):
                branches.add(line.split(" ", 1)[1].replace("refs/heads/", ""))
        return branches
    except (subprocess.SubprocessError, OSError):
        return set()


def cleanup_orphaned_branches():
    import os
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        subprocess.run(["git", "fetch", "--prune"], capture_output=True, timeout=30, env=env)
    except (subprocess.SubprocessError, OSError):
        pass

    base_branch = get_config().get("base_branch", "")
    closed = _get_done_task_ids()
    in_use = _worktree_branches()

    result = subprocess.run(
        ["git", "branch", "--list", "feature/*"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            branch = line.strip().lstrip("+* ")
            if not branch or branch in in_use:
                continue
            remote_check = subprocess.run(
                ["git", "rev-parse", "--verify", f"origin/{branch}"],
                capture_output=True, timeout=5,
            )
            if remote_check.returncode != 0:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    capture_output=True, timeout=10,
                )
                log(f"Deleted orphaned local branch: {branch}", "🧹")

    result = subprocess.run(
        ["git", "branch", "-r", "--list", "origin/feature/*"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return
    for line in result.stdout.strip().splitlines():
        ref = line.strip()
        if not ref:
            continue
        branch = ref.removeprefix("origin/")
        if branch == base_branch:
            continue
        task_id = branch.removeprefix("feature/")
        if task_id in closed:
            if _delete_remote_branch(branch):
                _delete_tracking_ref(branch)
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    capture_output=True, timeout=10,
                )
                log(f"Deleted stale remote branch: {branch}", "🧹")


def cleanup_stale_worktrees():
    subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
    repo = repo_root()
    wt_dir = repo / WORKTREES_DIR
    if not wt_dir.exists():
        return

    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=10,
    )
    active_paths = set()
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            active_paths.add(Path(line.split(" ", 1)[1]).resolve())

    for child in wt_dir.iterdir():
        if child.is_dir() and child.resolve() not in active_paths:
            _remove_symlinks(child)
            shutil.rmtree(child, ignore_errors=True)
            log(f"Cleaned stale worktree: {child.name}", "🧹")


def _delete_remote_branch(branch: str) -> bool:
    result = subprocess.run(
        ["git", "push", "--no-verify", "origin", "--delete", branch],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode == 0:
        return True
    if "remote ref does not exist" in result.stderr:
        return True
    log(f"Failed to delete remote branch {branch}: {result.stderr.strip()}", "⚠️")
    return False


def _delete_tracking_ref(branch: str):
    subprocess.run(
        ["git", "update-ref", "-d", f"refs/remotes/origin/{branch}"],
        capture_output=True, timeout=5,
    )


def delete_task_branch(task_id: str) -> None:
    """Delete a developer's feature branch locally if it exists."""
    branch = f"feature/{task_id}"
    if _branch_exists(branch):
        _remove_worktree_for_branch(branch)
        subprocess.run(
            ["git", "branch", "-D", branch],
            capture_output=True, timeout=10,
        )
        log(f"Deleted task branch: {branch}", "🧹")


def delete_branch(branch: str):
    subprocess.run(
        ["git", "branch", "-D", branch],
        capture_output=True, timeout=10,
    )
    _delete_remote_branch(branch)
    _delete_tracking_ref(branch)


def remove_all_worktrees():
    repo = repo_root()
    wt_dir = repo / WORKTREES_DIR
    if not wt_dir.exists():
        return

    for child in wt_dir.iterdir():
        if child.is_dir():
            _remove_symlinks(child)
            shutil.rmtree(child, ignore_errors=True)

    subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)

    if wt_dir.exists():
        shutil.rmtree(wt_dir, ignore_errors=True)
