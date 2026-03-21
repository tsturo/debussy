"""Tests for git worktree lifecycle management."""

import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from debussy.worktree import (
    WORKTREES_DIR,
    _branch_exists,
    _remove_symlinks,
    _symlink_dirs,
    _worktree_path,
    cleanup_stale_worktrees,
    create_worktree,
    delete_task_branch,
    remove_worktree,
)


def _git(repo: Path, *args, **kwargs):
    """Run git in the given repo."""
    return subprocess.run(
        ["git", *args],
        capture_output=True, text=True, timeout=10,
        cwd=str(repo), **kwargs,
    )


@pytest.fixture
def git_repo(tmp_path):
    """Create a real git repo with an initial commit and a fake origin."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "master")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    # Create a bare "origin" and push to it
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "origin")
    _git(repo, "branch", "--set-upstream-to=origin/master", "master")

    # Create .takt and .debussy dirs for symlink tests
    (repo / ".takt").mkdir()
    (repo / ".debussy").mkdir()

    return repo


@pytest.fixture(autouse=True)
def patch_repo_root(git_repo, monkeypatch):
    """Patch repo_root() to return our test repo and chdir into it."""
    monkeypatch.chdir(git_repo)
    with patch("debussy.worktree.repo_root", return_value=git_repo):
        yield


# --- _symlink_dirs ---

class TestSymlinkDirs:
    def test_creates_symlinks_for_takt_and_debussy(self, git_repo):
        wt = git_repo / WORKTREES_DIR / "test-agent"
        wt.mkdir(parents=True)
        _symlink_dirs(wt, git_repo)
        assert (wt / ".takt").is_symlink()
        assert (wt / ".debussy").is_symlink()
        assert (wt / ".takt").resolve() == (git_repo / ".takt").resolve()

    def test_skips_symlink_if_src_missing(self, git_repo):
        shutil.rmtree(git_repo / ".takt")
        wt = git_repo / WORKTREES_DIR / "test-agent"
        wt.mkdir(parents=True)
        _symlink_dirs(wt, git_repo)
        assert not (wt / ".takt").exists()
        assert (wt / ".debussy").is_symlink()

    def test_skips_symlink_if_dest_exists(self, git_repo):
        wt = git_repo / WORKTREES_DIR / "test-agent"
        wt.mkdir(parents=True)
        (wt / ".takt").mkdir()
        _symlink_dirs(wt, git_repo)
        assert not (wt / ".takt").is_symlink()  # kept as dir, not replaced

    def test_rejects_path_outside_worktrees_dir(self, git_repo):
        outside = git_repo / "not-a-worktree"
        outside.mkdir()
        with pytest.raises(RuntimeError, match="Refusing to symlink"):
            _symlink_dirs(outside, git_repo)


# --- _remove_symlinks ---

class TestRemoveSymlinks:
    def test_removes_existing_symlinks(self, git_repo):
        wt = git_repo / WORKTREES_DIR / "test-agent"
        wt.mkdir(parents=True)
        (wt / ".takt").symlink_to(git_repo / ".takt")
        (wt / ".debussy").symlink_to(git_repo / ".debussy")
        _remove_symlinks(wt)
        assert not (wt / ".takt").exists()
        assert not (wt / ".debussy").exists()

    def test_ignores_nonexistent_symlinks(self, git_repo):
        wt = git_repo / WORKTREES_DIR / "test-agent"
        wt.mkdir(parents=True)
        _remove_symlinks(wt)  # should not raise


# --- create_worktree / remove_worktree ---

class TestCreateRemoveWorktree:
    def test_create_detached_worktree(self, git_repo):
        wt = create_worktree("agent-bach", "master", detach=True)
        assert wt.exists()
        assert (wt / "README.md").exists()
        assert (wt / ".takt").is_symlink()
        assert (wt / ".debussy").is_symlink()

    def test_create_new_branch_worktree(self, git_repo):
        wt = create_worktree("agent-mozart", "feature/TST-1",
                             start_point="master", new_branch=True)
        assert wt.exists()
        # Verify the branch was created
        assert _branch_exists("feature/TST-1")

    def test_create_new_branch_without_start_point(self, git_repo):
        wt = create_worktree("agent-chopin", "feature/TST-2", new_branch=True)
        assert wt.exists()
        assert _branch_exists("feature/TST-2")

    def test_remove_worktree_cleans_up(self, git_repo):
        wt = create_worktree("agent-liszt", "master", detach=True)
        assert wt.exists()
        remove_worktree("agent-liszt")
        assert not wt.exists()

    def test_remove_nonexistent_worktree_is_noop(self, git_repo):
        remove_worktree("nonexistent-agent")  # should not raise

    def test_create_worktree_replaces_existing(self, git_repo):
        wt1 = create_worktree("agent-brahms", "master", detach=True)
        (wt1 / "marker.txt").write_text("first")
        wt2 = create_worktree("agent-brahms", "master", detach=True)
        assert wt2.exists()
        assert not (wt2 / "marker.txt").exists()  # fresh worktree

    def test_new_branch_already_exists_falls_back_to_checkout(self, git_repo):
        # Create the branch first
        _git(git_repo, "branch", "feature/TST-3")
        # Now try to create a worktree with new_branch=True — should not fail
        wt = create_worktree("agent-wagner", "feature/TST-3", new_branch=True)
        assert wt.exists()


# --- cleanup_stale_worktrees ---

class TestCleanupStaleWorktrees:
    def test_removes_directories_not_known_to_git(self, git_repo):
        wt_dir = git_repo / WORKTREES_DIR
        wt_dir.mkdir(parents=True, exist_ok=True)
        stale = wt_dir / "stale-agent"
        stale.mkdir()
        (stale / "somefile.txt").write_text("stale")

        cleanup_stale_worktrees()
        assert not stale.exists()

    def test_preserves_active_worktrees(self, git_repo):
        wt = create_worktree("agent-vivaldi", "master", detach=True)
        cleanup_stale_worktrees()
        assert wt.exists()

    def test_noop_when_worktrees_dir_missing(self, git_repo):
        cleanup_stale_worktrees()  # should not raise


# --- delete_task_branch ---

class TestDeleteTaskBranch:
    def test_deletes_local_branch(self, git_repo):
        _git(git_repo, "branch", "feature/TST-10")
        assert _branch_exists("feature/TST-10")
        delete_task_branch("TST-10")
        assert not _branch_exists("feature/TST-10")

    def test_noop_when_branch_missing(self, git_repo):
        delete_task_branch("TST-999")  # should not raise

    def test_removes_worktree_holding_the_branch(self, git_repo):
        wt = create_worktree("agent-ravel", "feature/TST-11",
                             start_point="master", new_branch=True)
        assert wt.exists()
        delete_task_branch("TST-11")
        assert not wt.exists()
        assert not _branch_exists("feature/TST-11")


# --- _branch_exists ---

class TestBranchExists:
    def test_detects_local_branch(self, git_repo):
        _git(git_repo, "branch", "feature/test-local")
        assert _branch_exists("feature/test-local") is True

    def test_returns_false_for_missing_branch(self, git_repo):
        assert _branch_exists("feature/nonexistent") is False

    def test_detects_remote_branch(self, git_repo):
        assert _branch_exists("master") is True  # origin/master exists


# --- _worktree_path ---

class TestWorktreePath:
    def test_returns_expected_path(self, git_repo):
        path = _worktree_path("agent-debussy")
        assert path == git_repo / WORKTREES_DIR / "agent-debussy"


# --- Integration: create → use → cleanup lifecycle ---

class TestWorktreeLifecycle:
    def test_developer_lifecycle(self, git_repo):
        """Simulate: create dev worktree → make commits → remove → cleanup."""
        wt = create_worktree("dev-bach", "feature/TST-20",
                             start_point="master", new_branch=True)
        assert wt.exists()

        # Simulate developer work
        (wt / "new_file.py").write_text("print('hello')")
        _git(wt, "add", ".")
        _git(wt, "commit", "-m", "add feature")

        # Remove worktree (agent finished)
        remove_worktree("dev-bach")
        assert not wt.exists()

        # Branch should still exist (only worktree removed)
        assert _branch_exists("feature/TST-20")

    def test_developer_death_cleanup(self, git_repo):
        """Simulate: create dev worktree → agent dies → delete_task_branch cleans both."""
        wt = create_worktree("dev-mozart", "feature/TST-21",
                             start_point="master", new_branch=True)
        assert wt.exists()

        # Agent dies, watcher calls delete_task_branch
        delete_task_branch("TST-21")
        assert not wt.exists()
        assert not _branch_exists("feature/TST-21")

    def test_reviewer_lifecycle(self, git_repo):
        """Simulate: create reviewer worktree (detached) → review → remove."""
        # First create a feature branch to review
        _git(git_repo, "checkout", "-b", "feature/TST-22")
        (git_repo / "feature.py").write_text("code")
        _git(git_repo, "add", ".")
        _git(git_repo, "commit", "-m", "feature")
        _git(git_repo, "push", "origin", "feature/TST-22")
        _git(git_repo, "checkout", "master")

        # Reviewer gets detached worktree
        wt = create_worktree("reviewer-bach", "origin/feature/TST-22", detach=True)
        assert wt.exists()
        assert (wt / "feature.py").exists()

        # Cleanup
        remove_worktree("reviewer-bach")
        assert not wt.exists()

    def test_respawn_after_death_gets_fresh_branch(self, git_repo):
        """After delete_task_branch, a new create_worktree gets a clean branch."""
        wt1 = create_worktree("dev-a", "feature/TST-23",
                              start_point="master", new_branch=True)
        (wt1 / "dirty.txt").write_text("partial work")
        _git(wt1, "add", ".")
        _git(wt1, "commit", "-m", "partial")

        # Agent dies
        delete_task_branch("TST-23")
        assert not _branch_exists("feature/TST-23")

        # Respawn — should get a fresh branch from master, not the old partial one
        wt2 = create_worktree("dev-b", "feature/TST-23",
                              start_point="master", new_branch=True)
        assert wt2.exists()
        assert not (wt2 / "dirty.txt").exists()  # fresh from master

    def test_multiple_concurrent_worktrees(self, git_repo):
        """Multiple worktrees can exist simultaneously without interference."""
        wt1 = create_worktree("dev-1", "feature/TST-30",
                              start_point="master", new_branch=True)
        wt2 = create_worktree("dev-2", "feature/TST-31",
                              start_point="master", new_branch=True)
        wt3 = create_worktree("rev-1", "master", detach=True)

        assert wt1.exists() and wt2.exists() and wt3.exists()

        # Each has its own symlinks
        for wt in (wt1, wt2, wt3):
            assert (wt / ".takt").is_symlink()
            assert (wt / ".debussy").is_symlink()

        # Cleanup one doesn't affect others
        remove_worktree("dev-1")
        assert not wt1.exists()
        assert wt2.exists() and wt3.exists()

        remove_worktree("dev-2")
        remove_worktree("rev-1")

    def test_cleanup_stale_preserves_active_removes_stale(self, git_repo):
        """cleanup_stale_worktrees keeps active ones, removes filesystem-only dirs."""
        active = create_worktree("active-agent", "master", detach=True)

        stale = git_repo / WORKTREES_DIR / "dead-agent"
        stale.mkdir(parents=True, exist_ok=True)
        (stale / ".takt").symlink_to(git_repo / ".takt")

        cleanup_stale_worktrees()

        assert active.exists()
        assert not stale.exists()
