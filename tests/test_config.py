"""Regression tests for the on-disk config layer."""

import pytest

from debussy.config import KNOWN_KEYS, clean_config, get_config, role_cli_args, set_config


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


def test_role_cli_args_omits_unset_effort(project_dir):
    set_config("role_efforts", {})
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5"]
