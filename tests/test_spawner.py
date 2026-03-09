"""Tests for agent spawning."""

import unittest
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

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="developer-bach")
    def test_spawn_aborts_when_worktree_fails_for_developer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "developer", "bd-001", "stage:development")

        self.assertFalse(result)
        self.assertEqual(watcher.failures.get("bd-001", 0), 1)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_reviewer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "reviewer", "bd-001", "stage:reviewing")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="integrator-bach")
    def test_spawn_aborts_when_worktree_fails_for_integrator(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "integrator", "bd-001", "stage:merging")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="tester-bach")
    def test_spawn_aborts_when_worktree_fails_for_tester(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "tester", "bd-001", "stage:acceptance")

        self.assertFalse(result)

    @patch("debussy.spawner.create_agent_worktree", return_value="")
    @patch("debussy.spawner.get_agent_name", return_value="security-reviewer-bach")
    def test_spawn_aborts_when_worktree_fails_for_security_reviewer(self, _name, _wt):
        from debussy.spawner import spawn_agent

        watcher = self._make_watcher()
        result = spawn_agent(watcher, "security-reviewer", "bd-001", "stage:security-review")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
