"""Watcher quota pause/resume state machine (methods tested in isolation)."""

import types

import pytest

from debussy import watcher as watcher_mod
from debussy.watcher import Watcher
from debussy.quota import QuotaStatus


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _blank_watcher():
    w = Watcher.__new__(Watcher)
    w.running = {}
    w.used_names = set()
    w._cached_windows = None
    w._last_quota_check = 0.0
    w._quota_warned = 0.0
    w.failures = {}
    return w


def test_enter_quota_pause_sets_state(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._enter_quota_pause(1500.0, "quota")
    cfg = get_config()
    assert cfg["paused"] is True
    assert cfg["pause_reason"] == "quota"
    assert cfg["paused_until"] == 1500.0


def test_enter_quota_pause_resolves_none_via_ccusage(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 2222.0, 9, 10))
    w._enter_quota_pause(None, "wall-hit")
    assert get_config()["paused_until"] == 2222.0


def test_enter_quota_pause_falls_back_to_cooldown(project_dir, monkeypatch):
    from debussy.config import get_config
    w = _blank_watcher()
    monkeypatch.setattr(w, "_pause_running_agents", lambda comment: None)
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: None)
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._enter_quota_pause(None, "wall-hit")
    assert get_config()["paused_until"] == 1000.0 + 3600


def test_auto_resume_noop_before_reset(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 5000.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._maybe_auto_resume()
    assert get_config()["paused"] is True


def test_auto_resume_clears_when_quota_back(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 500.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(False, 9000.0, 1, 10))
    w._maybe_auto_resume()
    assert get_config()["paused"] is False
    assert get_config().get("pause_reason") is None


def test_auto_resume_extends_when_still_capped(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 500.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 8000.0, 10, 10))
    w._maybe_auto_resume()
    assert get_config()["paused"] is True
    assert get_config()["paused_until"] == 8000.0


def test_auto_resume_ignores_manual_pause(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "manual")
    set_config("paused_until", 100.0); set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)
    w._maybe_auto_resume()
    assert get_config()["paused"] is True


def test_auto_resume_releases_when_feature_disabled(project_dir, monkeypatch):
    from debussy.config import set_config, get_config
    set_config("paused", True); set_config("pause_reason", "quota")
    set_config("paused_until", 100.0); set_config("quota_check", False)
    w = _blank_watcher()
    w._maybe_auto_resume()
    assert get_config()["paused"] is False


def test_pause_running_agents_stops_and_clears(project_dir, monkeypatch):
    w = _blank_watcher()
    stopped = []
    agent = types.SimpleNamespace(
        task="PRJ-2", role="reviewer", name="reviewer-y",
        worktree_path="", window_id="",
    )
    agent.stop = lambda: stopped.append(agent.name)
    agent.cleanup = lambda: None
    w.running = {"reviewer:PRJ-2": agent}
    w.used_names = {"reviewer-y"}
    monkeypatch.setattr(watcher_mod, "get_task_status", lambda t: "pending")
    monkeypatch.setattr(w, "save_state", lambda: None)
    w._pause_running_agents("paused: test")
    assert stopped == ["reviewer-y"]
    assert w.running == {}


def test_quota_gate_disabled_returns_none(project_dir):
    w = _blank_watcher()
    assert w._quota_gate() is None  # quota_check defaults to False


def test_quota_gate_respects_interval(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    w._last_quota_check = 999.0
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 1000.0)  # <60s since last
    called = []
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: called.append(1))
    assert w._quota_gate() is None
    assert called == []


def test_quota_gate_returns_status_when_exhausted(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(True, 5.0, 10, 10))
    status = w._quota_gate()
    assert status is not None and status.exhausted is True


def test_quota_gate_none_when_healthy(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota",
                        lambda *a: QuotaStatus(False, 5.0, 1, 10))
    assert w._quota_gate() is None


def test_quota_gate_warns_and_returns_none_on_unavailable(project_dir, monkeypatch):
    from debussy.config import set_config
    set_config("quota_check", True)
    w = _blank_watcher()
    monkeypatch.setattr(watcher_mod.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(watcher_mod, "check_quota", lambda *a: None)
    warned = []
    monkeypatch.setattr(w, "_warn_quota_unavailable", lambda now: warned.append(now))
    assert w._quota_gate() is None
    assert warned == [10_000.0]
