"""Regression tests for the on-disk config layer."""

import pytest

from debussy.config import DEFAULTS, KNOWN_KEYS, clean_config, get_config, role_cli_args, set_config


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("key", sorted(KNOWN_KEYS))
def test_known_keys_survive_clean_config(project_dir, key):
    """Every key in KNOWN_KEYS must persist across a clean_config() round-trip.

    The integrator's bounded auto-resolve path consults
    `debussy config test_command` as a fallback. `clean_config()` runs on
    every `debussy start` and wipes any key not in KNOWN_KEYS, so a
    refactor that drops a key would silently delete operator settings
    on the next start.
    """
    if isinstance(DEFAULTS.get(key), dict):
        set_config(key, {"probe": "sentinel-value"})
        clean_config()
        assert get_config()[key]["probe"] == "sentinel-value"
    else:
        set_config(key, "sentinel-value")
        clean_config()
        assert get_config().get(key) == "sentinel-value"


def test_clean_config_removes_unknown_keys(project_dir):
    set_config("not_a_real_key_xyz", "trash")
    clean_config()
    assert "not_a_real_key_xyz" not in get_config()


def test_test_command_is_a_known_key():
    assert "test_command" in KNOWN_KEYS


def test_autonomy_defaults_to_auto(project_dir):
    assert get_config()["autonomy"] == "auto"


def test_role_models_default_to_current_generation(project_dir):
    assert get_config()["role_models"] == {
        "conductor": "claude-fable-5",
        "developer": "claude-sonnet-5",
        "reviewer": "claude-opus-4-8",
        "security-reviewer": "claude-fable-5",
        "integrator": "claude-sonnet-5",
        "tester": "claude-sonnet-5",
    }


def test_role_efforts_cover_same_roles_as_role_models(project_dir):
    cfg = get_config()
    assert set(cfg["role_efforts"]) == set(cfg["role_models"])


def test_role_cli_args_returns_model_and_effort(project_dir):
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5", "--effort", "medium"]


def test_role_cli_args_empty_for_unknown_role(project_dir):
    assert role_cli_args("no-such-role") == []


def test_role_cli_args_omits_effort_disabled_per_role(project_dir):
    set_config("role_efforts", {"developer": ""})
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5"]


def test_role_cli_args_empty_for_non_claude_provider(project_dir):
    assert role_cli_args("developer", "other-cli") == []


def test_dict_config_values_deep_merge_with_defaults(project_dir):
    set_config("role_models", {"developer": "custom-model"})
    cfg = get_config()
    assert cfg["role_models"]["developer"] == "custom-model"
    assert cfg["role_models"]["reviewer"] == "claude-opus-4-8"
    assert cfg["role_efforts"]["developer"] == "medium"


def test_scalar_config_values_still_override(project_dir):
    set_config("max_total_agents", 3)
    assert get_config()["max_total_agents"] == 3


def test_non_dict_override_of_dict_key_falls_back_to_defaults(project_dir):
    set_config("role_models", "sonnet")
    assert get_config()["role_models"]["developer"] == "claude-sonnet-5"
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5", "--effort", "medium"]


def test_quota_defaults(project_dir):
    cfg = get_config()
    assert cfg["quota_check"] is False
    assert cfg["quota_margin"] == 0.97
    assert cfg["quota_command"] == "ccusage blocks --active --json --token-limit max"


@pytest.mark.parametrize("key", [
    "quota_check", "quota_command", "quota_margin", "pause_reason", "paused_until",
])
def test_quota_keys_known(key):
    assert key in KNOWN_KEYS


def test_quota_margin_config_round_trips_to_float(project_dir):
    from debussy.config import parse_value
    assert parse_value("0.9") == 0.9
    assert isinstance(parse_value("0.9"), float)
    set_config("quota_margin", parse_value("0.9"))
    assert get_config()["quota_margin"] == 0.9


def test_config_cache_distinguishes_directories_with_same_mtime(tmp_path, monkeypatch):
    import os

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    monkeypatch.chdir(dir_a)
    set_config("autonomy", "manual")
    monkeypatch.chdir(dir_b)
    set_config("autonomy", "auto")
    same_time = (1_700_000_000, 1_700_000_000)
    os.utime(dir_a / ".debussy" / "config.json", same_time)
    os.utime(dir_b / ".debussy" / "config.json", same_time)
    monkeypatch.chdir(dir_a)
    assert get_config()["autonomy"] == "manual"
    monkeypatch.chdir(dir_b)
    assert get_config()["autonomy"] == "auto"
