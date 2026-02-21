"""Git worktree lifecycle management for parallel agent isolation."""

import json
import shutil
import subprocess
from pathlib import Path

from .config import STATUS_CLOSED, get_config, log

WORKTREES_DIR = ".debussy-worktrees"


def _remove_symlinks(worktree_path: Path):
    for name in (".beads", ".debussy"):
        link = worktree_path / name
        if link.is_symlink():
            link.unlink()


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=5,
    )
    return Path(result.stdout.strip())


def _worktree_path(agent_name: str) -> Path:
    return _repo_root() / WORKTREES_DIR / agent_name


def _symlink_dirs(worktree: Path, repo: Path):
    for name in (".beads", ".debussy"):
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
    wt_dir = _repo_root() / WORKTREES_DIR
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


def create_worktree(agent_name: str, branch: str, start_point: str | None = None, new_branch: bool = False, detach: bool = False) -> Path:
    wt_path = _worktree_path(agent_name)
    repo = _repo_root()

    subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)

    if wt_path.exists():
        remove_worktree(agent_name)

    if not detach:
        _remove_worktree_for_branch(branch)

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    if detach:
        cmd = ["git", "worktree", "add", "--detach", str(wt_path), branch]
    elif new_branch:
        if _branch_exists(branch):
            cmd = ["git", "worktree", "add", str(wt_path), branch]
        else:
            cmd = ["git", "worktree", "add", "-b", branch, str(wt_path)]
            if start_point:
                cmd.append(start_point)
    else:
        cmd = ["git", "worktree", "add", str(wt_path), branch]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 and new_branch and start_point:
        subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
        if _branch_exists(branch):
            subprocess.run(["git", "branch", "-D", branch], capture_output=True, timeout=10)
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
        cmd = ["git", "worktree", "add", "-b", branch, str(wt_path), start_point]
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


def _get_closed_bead_ids() -> set[str]:
    try:
        result = subprocess.run(
            ["bd", "list", "--status", STATUS_CLOSED, "--limit", "0", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return set()
        beads = json.loads(result.stdout)
        return {b.get("id") for b in beads if b.get("id")}
    except (subprocess.SubprocessError, OSError, ValueError):
        return set()


def cleanup_orphaned_branches():
    subprocess.run(["git", "fetch", "--prune"], capture_output=True, timeout=30)

    base_branch = get_config().get("base_branch", "")
    closed = _get_closed_bead_ids()

    result = subprocess.run(
        ["git", "branch", "--list", "feature/*"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            branch = line.strip().lstrip("+* ")
            if not branch:
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
        bead_id = branch.removeprefix("feature/")
        if bead_id in closed:
            subprocess.run(
                ["git", "push", "origin", "--delete", branch],
                capture_output=True, timeout=15,
            )
            subprocess.run(
                ["git", "branch", "-D", branch],
                capture_output=True, timeout=10,
            )
            log(f"Deleted stale remote branch: {branch}", "🧹")


def cleanup_stale_worktrees():
    subprocess.run(["git", "worktree", "prune"], capture_output=True, timeout=10)
    repo = _repo_root()
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
            active_paths.add(Path(line.split(" ", 1)[1]))

    for child in wt_dir.iterdir():
        if child.is_dir() and child.resolve() not in active_paths:
            _remove_symlinks(child)
            shutil.rmtree(child, ignore_errors=True)
            log(f"Cleaned stale worktree: {child.name}", "🧹")


def delete_branch(branch: str):
    subprocess.run(
        ["git", "branch", "-D", branch],
        capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "push", "origin", "--delete", branch],
        capture_output=True, timeout=15,
    )


def remove_all_worktrees():
    repo = _repo_root()
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
