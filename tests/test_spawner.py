"""Tests for agent spawning."""

import os
import shutil
import subprocess
import tempfile
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
    @patch("debussy.spawner.get_agent_name", return_value="security-reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_security_reviewer(self, _name, _wt, _pf):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "security-reviewer", "bd-001", "stage:security_review")

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
    @patch("debussy.spawner._takt_log")
    @patch("debussy.spawner.get_db")
    @patch("debussy.spawner._spawn_background")
    def test_spawn_proceeds_after_preflight_passes(
        self, mock_bg, _db, _log, _cfg, _sys, _msg, _base, _name, _wt, _preflight
    ):
        from debussy.spawner import spawn_agent

        mock_bg.return_value = MagicMock()
        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertTrue(result)


class TestSpawnCommandFlags(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    @patch("debussy.spawner.subprocess.run")
    @patch("debussy.spawner.role_cli_args", return_value=["--model", "claude-sonnet-5", "--effort", "medium"])
    @patch("debussy.spawner.get_config", return_value={"agent_provider": "claude"})
    def test_tmux_command_includes_model_and_effort(self, _cfg, _args, mock_run):
        from debussy.spawner import _spawn_tmux

        mock_run.return_value = MagicMock(stdout="@42\n", returncode=0)
        _spawn_tmux("developer-bach", "bd-1", "developer", Path("/tmp/p.md"), "msg", "stage:development")

        shell_cmd = mock_run.call_args_list[0][0][0][-1]
        self.assertIn("--model claude-sonnet-5", shell_cmd)
        self.assertIn("--effort medium", shell_cmd)

    @patch("debussy.spawner.subprocess.Popen")
    @patch("debussy.spawner.role_cli_args", return_value=["--model", "claude-sonnet-5", "--effort", "medium"])
    @patch("debussy.spawner.get_config", return_value={"agent_provider": "claude"})
    def test_background_command_includes_model_and_effort(self, _cfg, _args, mock_popen):
        from debussy.spawner import _spawn_background

        _spawn_background("developer-bach", "bd-1", "developer", "sys", "msg", "stage:development")

        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-sonnet-5")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")


if __name__ == "__main__":
    unittest.main()
