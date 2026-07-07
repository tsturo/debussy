"""Pause-state markers set by the CLI pause/resume/start commands."""

import types

import pytest

from debussy import cli
from debussy.config import get_config


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_pause_sets_manual_reason(project_dir, monkeypatch):
    monkeypatch.setattr(cli, "_kill_all_agents", lambda: None)
    cli.cmd_pause(types.SimpleNamespace())
    cfg = get_config()
    assert cfg["paused"] is True
    assert cfg["pause_reason"] == "manual"
    assert cfg.get("paused_until") is None


def test_resume_clears_quota_markers(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("pause_reason", "quota")
    set_config("paused_until", 123.0)
    cli.cmd_resume(types.SimpleNamespace())
    cfg = get_config()
    assert cfg["paused"] is False
    assert cfg.get("pause_reason") is None
    assert cfg.get("paused_until") is None
