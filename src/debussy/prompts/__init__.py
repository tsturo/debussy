"""Agent prompt templates."""

from ..config import get_base_branch, get_config
from .conductor import CONDUCTOR_PROMPT
from .developer import developer_prompt
from .integrator import integrator_prompt
from .investigator import investigator_prompt
from .reviewer import reviewer_prompt
from .security_reviewer import security_reviewer_prompt
from .tester import tester_prompt

__all__ = ["get_prompt", "get_conductor_prompt"]

_NO_BRANCH_ERROR = (
    "ERROR: No base branch configured. The conductor must create a feature branch first.\n"
    "Run: debussy config base_branch <branch-name>\n"
    "Exit immediately."
)

_BUILDERS = {
    "developer": lambda bead_id, base, stage, labels: developer_prompt(bead_id, base, labels=labels),
    "reviewer": lambda bead_id, base, stage, labels: reviewer_prompt(bead_id, base),
    "security-reviewer": lambda bead_id, base, stage, labels: security_reviewer_prompt(bead_id, base),
    "tester": lambda bead_id, base, stage, labels: tester_prompt(bead_id, base, stage),
    "integrator": lambda bead_id, base, stage, labels: integrator_prompt(bead_id, base, stage),
    "investigator": lambda bead_id, base, stage, labels: investigator_prompt(bead_id, base, stage),
}

_ROLE_DOC_FOCUS = {
    "conductor": "all documentation — requirements, architecture, glossary, and constraints",
    "developer": "requirements, API specs, and data models relevant to your bead",
    "reviewer": "architecture, conventions, and constraints to validate implementation choices",
    "security-reviewer": "security policies, auth specs, and data flow documentation",
    "tester": "acceptance criteria, expected behaviors, and integration specs",
    "investigator": "architecture and domain docs to understand the system",
}


def _docs_block(role: str, docs_path: str) -> str:
    focus = _ROLE_DOC_FOCUS.get(role)
    if not focus:
        return ""
    return (
        f"\n\nDOCUMENTATION REVIEW (do this before implementation):\n"
        f"Review project documentation at: {docs_path}\n"
        f"As a {role}, focus on: {focus}.\n"
        f"List the directory, then read the most relevant files."
    )


def get_conductor_prompt() -> str:
    docs_path = get_config().get("docs_path")
    if not docs_path:
        return CONDUCTOR_PROMPT
    return CONDUCTOR_PROMPT + _docs_block("conductor", docs_path)


def get_prompt(role: str, bead_id: str, stage: str, labels: list[str] | None = None) -> str:
    base = get_base_branch()
    if not base and role not in ("investigator",):
        return _NO_BRANCH_ERROR

    builder = _BUILDERS.get(role)
    if not builder:
        raise ValueError(f"Unknown role: {role}")

    prompt = builder(bead_id, base, stage, labels or [])
    docs_path = get_config().get("docs_path")
    if docs_path:
        prompt += _docs_block(role, docs_path)
    return prompt
