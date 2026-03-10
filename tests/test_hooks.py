"""Tests for Claude Code hook management."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from debussy.hooks import install_hooks, uninstall_hooks


class TestInstallHooks:
    def test_creates_settings_file_when_missing(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        with patch("debussy.hooks.SETTINGS_FILE", settings):
            install_hooks()
        result = json.loads(settings.read_text())
        assert "PreCompact" in result["hooks"]

    def test_preserves_existing_hooks(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]
            }
        }))
        with patch("debussy.hooks.SETTINGS_FILE", settings):
            install_hooks()
        result = json.loads(settings.read_text())
        assert "Stop" in result["hooks"]
        assert "PreCompact" in result["hooks"]

    def test_does_not_duplicate_on_reinstall(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        with patch("debussy.hooks.SETTINGS_FILE", settings):
            install_hooks()
            install_hooks()
        result = json.loads(settings.read_text())
        assert len(result["hooks"]["PreCompact"]) == 1


class TestUninstallHooks:
    def test_removes_debussy_hooks(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        with patch("debussy.hooks.SETTINGS_FILE", settings):
            install_hooks()
            uninstall_hooks()
        result = json.loads(settings.read_text())
        assert "PreCompact" not in result.get("hooks", {})

    def test_preserves_non_debussy_hooks(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]
            }
        }))
        with patch("debussy.hooks.SETTINGS_FILE", settings):
            install_hooks()
            uninstall_hooks()
        result = json.loads(settings.read_text())
        assert "Stop" in result["hooks"]
