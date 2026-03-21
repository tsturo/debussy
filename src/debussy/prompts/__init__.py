"""Agent prompt templates."""

from pathlib import Path

from ..config import get_config

_PROMPTS_DIR = Path(__file__).parent

_VISUAL_BLOCKS = {
    "web": {
        "VISUAL_VERIFICATION_BLOCK": "visual_web.md",
        "REVIEWER_VISUAL_BLOCK": "visual_review_web.md",
        "TESTER_VISUAL_BLOCK": "visual_test_web.md",
    },
    "ios": {
        "VISUAL_VERIFICATION_BLOCK": "visual_ios.md",
        "REVIEWER_VISUAL_BLOCK": "visual_review_ios.md",
        "TESTER_VISUAL_BLOCK": "visual_test_ios.md",
    },
}

_ROLE_FILES = {
    "developer": "developer.md",
    "reviewer": "reviewer.md",
    "security-reviewer": "security-reviewer.md",
    "integrator": "integrator.md",
    "tester": "tester.md",
}

_ROLE_DOC_FOCUS = {
    "conductor": "all documentation — requirements, architecture, glossary, and constraints",
    "developer": "requirements, API specs, and data models relevant to your task",
    "reviewer": "architecture, conventions, and constraints to validate implementation choices",
    "security-reviewer": "security policies, auth specs, and data flow documentation",
    "tester": "acceptance criteria, expected behaviors, and integration specs",
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
    filename = _ROLE_FILES.get(role)
    if not filename:
        raise ValueError(f"Unknown role: {role}")
    return _PROMPTS_DIR / filename


def _detect_project_type() -> str | None:
    cfg_type = get_config().get("project_type")
    if cfg_type:
        return cfg_type
    cwd = Path.cwd()
    if list(cwd.glob("*.xcworkspace")) or list(cwd.glob("*.xcodeproj")):
        return "ios"
    if (cwd / "package.json").exists():
        return "web"
    return None


def _substitute_visual_blocks(text: str) -> str:
    project_type = _detect_project_type()
    blocks = _VISUAL_BLOCKS.get(project_type, {}) if project_type else {}
    for placeholder, filename in blocks.items():
        if placeholder in text:
            template = (_PROMPTS_DIR / filename).read_text()
            text = text.replace(placeholder, template)
    for placeholder in ("VISUAL_VERIFICATION_BLOCK", "REVIEWER_VISUAL_BLOCK", "TESTER_VISUAL_BLOCK"):
        text = text.replace(placeholder, "")
    return text


def get_system_prompt(role: str, stage: str) -> str:
    text = get_prompt_path(role, stage).read_text()
    return _substitute_visual_blocks(text)


def get_user_message(role: str, task_id: str, base: str, agent_name: str = "", labels: list[str] | None = None) -> str:
    if not base:
        return _NO_BRANCH_ERROR
    parts = [f"Task: {task_id}"]
    if agent_name:
        parts.append(f"Agent name: {agent_name}")
    if base:
        parts.append(f"Base branch: {base}")
    tags = [l for l in (labels or []) if not l.startswith("stage:")]
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    docs_path = get_config().get("docs_path")
    if docs_path:
        focus = _ROLE_DOC_FOCUS.get(role, "")
        parts.append(f"Documentation: {docs_path}" + (f" (focus: {focus})" if focus else ""))
    return "\n".join(parts)


def get_conductor_prompt_path() -> Path:
    return _PROMPTS_DIR / "conductor.md"


def get_conductor_system_prompt() -> str:
    text = get_conductor_prompt_path().read_text()
    interval = get_config().get("monitor_interval", 300)
    return text.replace("MONITOR_INTERVAL", str(interval))


def get_conductor_user_message(requirement: str | None = None) -> str:
    parts = []
    history_file = Path(".debussy/conductor-history.md")
    if history_file.exists() and history_file.read_text().strip():
        parts.append("Project history: read .debussy/conductor-history.md")
    context_file = Path(".debussy/conductor-context.md")
    if context_file.exists() and context_file.read_text().strip():
        parts.append("Previous session context: read .debussy/conductor-context.md")
    if requirement:
        parts.append(requirement)
    return "\n\n".join(parts) if parts else "Begin."
