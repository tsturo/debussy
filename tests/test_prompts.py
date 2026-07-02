"""Tests for conductor prompt assembly."""

import pytest

from debussy.config import set_config
from debussy.prompts import get_conductor_system_prompt


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_auto_mode_is_default(project_dir):
    text = get_conductor_system_prompt()
    assert "never ask the user mid-run" in text
    assert "AUTONOMY_INSTRUCTIONS" not in text


def test_manual_mode_injects_manual_instructions(project_dir):
    set_config("autonomy", "manual")
    text = get_conductor_system_prompt()
    assert "wait for the user's choice" in text
    assert "never ask the user mid-run" not in text


def test_unknown_autonomy_value_falls_back_to_auto(project_dir):
    set_config("autonomy", "bogus")
    text = get_conductor_system_prompt()
    assert "never ask the user mid-run" in text


def test_no_unsubstituted_placeholders(project_dir):
    text = get_conductor_system_prompt()
    assert "MONITOR_INTERVAL" not in text
    assert "AUTONOMY_INSTRUCTIONS" not in text


def test_supervision_sections_present(project_dir):
    text = get_conductor_system_prompt()
    assert "PIPELINE SUPERVISION" in text
    assert "DECISION PROTOCOL" in text
    assert "ESCALATION LADDER" in text
    assert "TERMINAL CHECK" in text


def test_parking_uses_parked_stage(project_dir):
    text = get_conductor_system_prompt()
    assert "takt advance <id> --to parked" in text
    assert "Never park an acceptance task" in text
