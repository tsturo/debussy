"""Static content assertions for the integrator agent prompt.

The integrator is a prompt-driven LLM agent, so behavioral tests against
an LLM are out of CI scope. These tests assert that the operational
definitions from spec 2026-04-28-pipeline-simplification-design.md
appear verbatim in the prompt — paraphrasing fails by design.
"""

from pathlib import Path

import pytest

PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "debussy"
    / "prompts"
    / "integrator.md"
)


@pytest.fixture(scope="module")
def prompt() -> str:
    return PROMPT_PATH.read_text()


def test_timeout_directive_present(prompt):
    assert (
        "EVERY Bash invocation that runs tests MUST include `timeout: 600000`"
        in prompt
    )


def test_when_in_doubt_block_present(prompt):
    assert "When in doubt, block" in prompt


def test_no_test_command_message_present(prompt):
    assert (
        "no test command discoverable; set `debussy config test_command` "
        "to enable auto-resolve for this project"
        in prompt
    )


@pytest.mark.parametrize(
    "lockfile",
    [
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "go.sum",
        "uv.lock",
        "bun.lockb",
    ],
)
def test_lockfile_listed(prompt, lockfile):
    assert lockfile in prompt


def test_old_reject_path_removed(prompt):
    assert "IF MERGE CONFLICTS cannot be resolved" not in prompt
    assert 'takt comment <TASK_ID> "Merge conflict: [details]"' not in prompt


def test_preserved_reject_paths_intact(prompt):
    assert "origin/feature/<TASK_ID> does not exist" in prompt
    assert "Push failed after retries" in prompt
