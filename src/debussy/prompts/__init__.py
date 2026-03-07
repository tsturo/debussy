"""Agent prompt templates."""

from pathlib import Path

from ..config import get_config, STAGE_CONSOLIDATING

_PROMPTS_DIR = Path(__file__).parent

_ROLE_FILES = {
    "developer": "developer.md",
    "reviewer": "reviewer.md",
    "security-reviewer": "security-reviewer.md",
    "integrator": "integrator.md",
    "tester": "tester.md",
    "investigator": "investigator.md",
}

_ROLE_DOC_FOCUS = {
    "conductor": "all documentation — requirements, architecture, glossary, and constraints",
    "developer": "requirements, API specs, and data models relevant to your bead",
    "reviewer": "architecture, conventions, and constraints to validate implementation choices",
    "security-reviewer": "security policies, auth specs, and data flow documentation",
    "tester": "acceptance criteria, expected behaviors, and integration specs",
    "investigator": "architecture and domain docs to understand the system",
}

_NO_BRANCH_ERROR = (
    "ERROR: No base branch configured. The conductor must create a feature branch first.\n"
    "Run: debussy config base_branch <branch-name>\n"
    "Exit immediately."
)

__all__ = [
    "get_prompt_path", "get_system_prompt", "get_user_message",
    "get_conductor_prompt_path", "get_conductor_system_prompt", "get_conductor_user_message",
]


def get_prompt_path(role: str, stage: str) -> Path:
    if role == "investigator" and stage == STAGE_CONSOLIDATING:
        return _PROMPTS_DIR / "consolidator.md"
    filename = _ROLE_FILES.get(role)
    if not filename:
        raise ValueError(f"Unknown role: {role}")
    return _PROMPTS_DIR / filename


def get_system_prompt(role: str, stage: str) -> str:
    return get_prompt_path(role, stage).read_text()


def get_user_message(role: str, bead_id: str, base: str, labels: list[str] | None = None) -> str:
    if not base and role not in ("investigator",):
        return _NO_BRANCH_ERROR
    parts = [f"Bead: {bead_id}"]
    if base:
        parts.append(f"Base branch: {base}")
    semantic_labels = [l for l in (labels or []) if not l.startswith("stage:")]
    if semantic_labels:
        parts.append(f"Labels: {', '.join(semantic_labels)}")
    docs_path = get_config().get("docs_path")
    if docs_path:
        focus = _ROLE_DOC_FOCUS.get(role, "")
        parts.append(f"Documentation: {docs_path}" + (f" (focus: {focus})" if focus else ""))
    return "\n".join(parts)


def get_conductor_prompt_path() -> Path:
    return _PROMPTS_DIR / "conductor.md"


def get_conductor_system_prompt() -> str:
    return get_conductor_prompt_path().read_text()


def get_conductor_user_message(requirement: str | None = None) -> str:
    parts = []
    context_file = Path(".debussy/conductor-context.md")
    if context_file.exists():
        context = context_file.read_text().strip()
        if context:
            parts.append(f"Previous session context:\n{context}")
    if requirement:
        parts.append(requirement)
    return "\n\n".join(parts) if parts else "Begin."
