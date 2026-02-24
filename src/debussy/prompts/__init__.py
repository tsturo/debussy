"""Agent prompt templates."""

from ..config import get_base_branch
from .conductor import CONDUCTOR_PROMPT
from .developer import developer_prompt
from .integrator import integrator_prompt
from .investigator import investigator_prompt
from .reviewer import reviewer_prompt
from .security_reviewer import security_reviewer_prompt
from .tester import tester_prompt

__all__ = ["get_prompt", "CONDUCTOR_PROMPT"]

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


def get_prompt(role: str, bead_id: str, stage: str, labels: list[str] | None = None) -> str:
    base = get_base_branch()
    if not base and role not in ("investigator",):
        return _NO_BRANCH_ERROR

    builder = _BUILDERS.get(role)
    if builder:
        return builder(bead_id, base, stage, labels or [])

    raise ValueError(f"Unknown role: {role}")
