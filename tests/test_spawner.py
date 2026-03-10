"""Tests for agent spawning."""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestSpawnAgentWorktreeFailure(unittest.TestCase):
    def _make_watcher(self):
        watcher = MagicMock()
        watcher.running = {}
        watcher.failures = {}
        watcher.spawn_counts = {}
        watcher.used_names = set()
        watcher._cached_windows = None
        return watcher

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="developer-bach")
    def test_spawn_aborts_when_worktree_fails_for_developer(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        watcher.used_names.add("developer-bach")
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertFalse(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 1)
        self.assertNotIn("developer-bach", watcher.used_names)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_reviewer(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "reviewer", "bd-001", "stage:reviewing")

        self.assertFalse(result)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="integrator-bach")
    def test_spawn_aborts_when_worktree_fails_for_integrator(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "integrator", "bd-001", "stage:merging")

        self.assertFalse(result)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="tester-bach")
    def test_spawn_aborts_when_worktree_fails_for_tester(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "tester", "bd-001", "stage:acceptance")

        self.assertFalse(result)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="security-reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_security_reviewer(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "security-reviewer", "bd-001", "stage:security-review")

        self.assertFalse(result)


    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.get_base_branch", return_value="master")
    @patch("debussy.spawner.get_user_message", return_value="test message")
    @patch("debussy.spawner.get_system_prompt", return_value="test prompt")
    @patch("debussy.spawner.get_config", return_value={"use_tmux_windows": False})
    @patch("debussy.spawner.record_event")
    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="investigator-bach")
    def test_spawn_proceeds_for_investigator_without_worktree(
        self, _name, _wt, _event, _cfg, _sys, _msg, _base, _pf
    ):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        with patch("debussy.spawner._spawn_background") as mock_spawn:
            mock_spawn.return_value = MagicMock()
            result = spawn_agent(watcher, "investigator", "bd-001", "stage:investigating")

        self.assertTrue(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 0)


class TestCreateAgentWorktreeRetry(unittest.TestCase):
    @patch("debussy.spawner.get_config", return_value={"base_branch": "master"})
    @patch("debussy.spawner.create_worktree")
    @patch("debussy.spawner.subprocess")
    def test_retries_once_after_failure(self, mock_subprocess, mock_create_wt, _cfg):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.SubprocessError = subprocess.SubprocessError
        mock_create_wt.side_effect = [
            subprocess.CalledProcessError(1, "git"),
            Path("/fake/worktree"),
        ]

        from debussy.spawner import create_agent_worktree

        result = create_agent_worktree("developer", "bd-001", "developer-bach")

        self.assertEqual(result, "/fake/worktree")
        self.assertEqual(mock_create_wt.call_count, 2)

    @patch("debussy.spawner.get_config", return_value={"base_branch": "master"})
    @patch("debussy.spawner.create_worktree")
    @patch("debussy.spawner.subprocess")
    def test_returns_empty_after_retry_failure(self, mock_subprocess, mock_create_wt, _cfg):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.SubprocessError = subprocess.SubprocessError
        mock_create_wt.side_effect = subprocess.CalledProcessError(1, "git")

        from debussy.spawner import create_agent_worktree

        result = create_agent_worktree("developer", "bd-001", "developer-bach")

        self.assertEqual(result, "")
        self.assertEqual(mock_create_wt.call_count, 2)


class TestSpawnAgentPreflight(unittest.TestCase):
    def _make_watcher(self):
        watcher = MagicMock()
        watcher.running = {}
        watcher.failures = {}
        watcher.spawn_counts = {}
        watcher.used_names = set()
        watcher._cached_windows = None
        return watcher

    @patch("debussy.spawner.preflight_spawn", return_value="base_branch not configured")
    def test_spawn_aborts_on_preflight_failure(self, _preflight):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertFalse(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 1)

    @patch("debussy.spawner.preflight_spawn", return_value=None)
    @patch("debussy.spawner.create_agent_worktree", return_value="/fake/wt")
    @patch("debussy.spawner.get_agent_name", return_value="developer-bach")
    @patch("debussy.spawner.get_base_branch", return_value="master")
    @patch("debussy.spawner.get_user_message", return_value="msg")
    @patch("debussy.spawner.get_system_prompt", return_value="prompt")
    @patch("debussy.spawner.get_config", return_value={"use_tmux_windows": False})
    @patch("debussy.spawner.record_event")
    @patch("debussy.spawner._spawn_background")
    def test_spawn_proceeds_after_preflight_passes(
        self, mock_bg, _event, _cfg, _sys, _msg, _base, _name, _wt, _preflight
    ):
        from debussy.spawner import spawn_agent

        mock_bg.return_value = MagicMock()
        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
