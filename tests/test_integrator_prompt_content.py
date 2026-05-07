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


def test_only_push_failure_path_uses_takt_reject(prompt):
    """The conflict path must `takt block`, never `takt reject`.

    Two reject sites are legitimate: developer-never-pushed (step 4) and
    push-retry-exhaustion. A regression that re-introduces conflict→reject
    would push this count to 3+.
    """
    assert prompt.count("takt reject <TASK_ID>") == 2


def test_block_precedes_permissive_in_conflict_section(prompt):
    """BLOCK conditions must be evaluated before (and override) permissive ones."""
    assert "Evaluate BLOCK conditions FIRST" in prompt


def test_test_discovery_order(prompt):
    """Auto-discovery order is pytest → make test → npm test → operator override."""
    assert (
        prompt.index("pytest")
        < prompt.index("make test")
        < prompt.index("npm test")
        < prompt.index("debussy config test_command")
    )
