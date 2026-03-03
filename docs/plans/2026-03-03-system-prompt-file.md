# System Prompt File Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace dynamically-built prompt strings passed as CLI arguments with static `.md` role files loaded via `--system-prompt-file`, passing only bead-specific context as the user message.

**Architecture:** Each agent role gets a static `.md` file in `src/debussy/prompts/`. The `get_prompt()` function is replaced by two helpers: one that returns the `.md` file path, one that builds a short user message from bead context. The spawner and tmux launcher are updated to use `--system-prompt-file <path> <user_message>`.

**Tech Stack:** Python, Claude CLI (`--system-prompt-file`), tmux

---

### Task 1: Create static `.md` files for all roles

**Files:**
- Create: `src/debussy/prompts/conductor.md`
- Create: `src/debussy/prompts/developer.md`
- Create: `src/debussy/prompts/reviewer.md`
- Create: `src/debussy/prompts/security-reviewer.md`
- Create: `src/debussy/prompts/integrator.md`
- Create: `src/debussy/prompts/tester.md`
- Create: `src/debussy/prompts/investigator.md`
- Create: `src/debussy/prompts/consolidator.md`

No Python changes yet — just create the files.

**Step 1: Create `conductor.md`**

Copy content verbatim from `CONDUCTOR_PROMPT` in `src/debussy/prompts/conductor.py`. No placeholders needed — conductor has no bead context. The `requirement` will be passed as the user message.

```markdown
You are @conductor - the orchestrator. NEVER write code yourself.
... (full CONDUCTOR_PROMPT content) ...
```

**Step 2: Create `developer.md`**

Extract the static instructions from `developer_prompt()` in `developer.py`. Replace `{bead_id}` with `<BEAD_ID>` and `{base}` with `<BASE_BRANCH>` throughout. Include the frontend block unconditionally but mark it conditional:

```markdown
You are an autonomous developer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Do NOT say "Would you like me to..." or similar. Just do the work.

EXECUTE THESE STEPS NOW:

1. bd show <BEAD_ID>
2. bd update <BEAD_ID> --status in_progress
3. git pull origin <BASE_BRANCH>
4. VERIFY: run `git branch --show-current` — must show `feature/<BEAD_ID>`. If not, STOP and set status blocked.
5. Implement the task — keep functions small and testable
6. If the bead description includes test criteria, write tests covering ALL of them. If no test criteria are specified, skip tests.
7. Run tests to verify they pass
8. SCOPE CHECK: run `git diff origin/<BASE_BRANCH>...HEAD --stat` — every changed file must be relevant to the bead description. Do NOT modify or delete files/tests that belong to other beads.
9. Commit and push changes
10. bd update <BEAD_ID> --status open
11. Exit

IMPORTANT: You are already on branch feature/<BEAD_ID>. Do NOT checkout other branches.

IF TASK IS TOO BIG (needs 3+ files, multiple behaviors, or you can't finish in one session):
  bd comment <BEAD_ID> "Too big — suggest splitting: 1) [subtask A] 2) [subtask B] ..."
  bd update <BEAD_ID> --status blocked
  Exit. Let conductor split it.

IF BLOCKED — dependencies missing, code you need doesn't exist yet, or requirements unclear:
  bd comment <BEAD_ID> "Blocked: [reason — what is missing or unclear]"
  bd update <BEAD_ID> --status blocked
  Exit immediately. Do NOT set status open with no commits.

IF YOU FIND AN UNRELATED BUG:
  bd comment <BEAD_ID> "Unrelated bug: [title] — [details]"
  Continue with your task. The conductor will triage it.

FRONTEND VISUAL VERIFICATION (only if this bead has the `frontend` label):

Before committing, perform visual verification:

A) START DEV SERVER:
   - Read the bead description for the dev server command (e.g., "Dev server: npm run dev (port 3000)")
   - If no dev server command is in the description:
     bd comment <BEAD_ID> "Blocked: no dev server command in bead description"
     bd update <BEAD_ID> --status blocked
     Exit immediately.
   - Start it in the background: <command> &
   - Wait for it to be ready: poll the URL until it responds (max 30 seconds)

B) VISUAL VERIFICATION LOOP (use Playwright MCP):
   - If the bead description mentions mobile, responsive, or mobile-first:
     browser_resize with width=390, height=844 (iPhone 14) before navigating
   - browser_navigate to the relevant page URL
   - browser_take_screenshot to capture the current state
   - Evaluate the screenshot against the bead description
   - Use browser_click, browser_fill_form, browser_hover to test interactions
   - If it looks wrong or incomplete, fix the code and repeat
   - Max 3 iterations — if still broken after 3, commit what you have and note issues in a comment

C) WRITE PLAYWRIGHT TESTS:
   - Create Playwright test file(s) that codify the visual/functional checks you just verified
   - Tests should cover: page loads, key elements visible, interactions work as described
   - For mobile/responsive beads: use devices['iPhone 14'] preset from @playwright/test
   - Run: npx playwright test <your-test-file>
   - Fix until tests pass

D) CLEANUP:
   - browser_close to close the Playwright browser
   - Kill the dev server process

SKILLS:
   - Invoke /frontend-design before implementing any UI work
   - Use Playwright MCP tools (browser_navigate, browser_take_screenshot, browser_click, browser_fill_form) for all visual verification — do NOT use npx playwright screenshot

START NOW. Do not wait for instructions. Begin with step 1.
```

**Step 3: Create `reviewer.md`**

Extract from `reviewer_prompt()`, replace `{bead_id}` → `<BEAD_ID>`, `{base}` → `<BASE_BRANCH>`.

**Step 4: Create `security-reviewer.md`**

Extract from `security_reviewer_prompt()`, same replacements.

**Step 5: Create `integrator.md`**

Extract from `integrator_prompt()`, same replacements.

**Step 6: Create `tester.md`**

Extract from `_batch_acceptance_prompt()`, same replacements.

**Step 7: Create `investigator.md`**

Extract from `_investigating_prompt()`, replace `{bead_id}` → `<BEAD_ID>`.

**Step 8: Create `consolidator.md`**

Extract from `_consolidating_prompt()`, replace `{bead_id}` → `<BEAD_ID>`.

**Step 9: Commit**

```bash
git add src/debussy/prompts/*.md
git commit -m "add static role prompt .md files"
```

---

### Task 2: Refactor `prompts/__init__.py`

**Files:**
- Modify: `src/debussy/prompts/__init__.py`

Replace `get_prompt()` and `get_conductor_prompt()` with two functions each:
- `get_prompt_file(role, stage)` → `Path` to the `.md` file
- `get_user_message(role, bead_id, base, stage, labels)` → short context string
- `get_conductor_prompt_file()` → `Path` to `conductor.md`
- `get_conductor_user_message(requirement)` → requirement string or `"Begin."`

**Step 1: Rewrite `__init__.py`**

```python
"""Agent prompt templates."""

from pathlib import Path

from ..config import get_base_branch, get_config, STAGE_CONSOLIDATING

_PROMPTS_DIR = Path(__file__).parent

_ROLE_FILES = {
    "developer": "developer.md",
    "reviewer": "reviewer.md",
    "security-reviewer": "security-reviewer.md",
    "integrator": "integrator.md",
    "tester": "tester.md",
    "investigator": "investigator.md",
    "consolidator": "consolidator.md",
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

__all__ = ["get_prompt_file", "get_user_message", "get_conductor_prompt_file", "get_conductor_user_message"]


def get_prompt_file(role: str, stage: str) -> Path:
    if role == "investigator" and stage == STAGE_CONSOLIDATING:
        return _PROMPTS_DIR / "consolidator.md"
    filename = _ROLE_FILES.get(role)
    if not filename:
        raise ValueError(f"Unknown role: {role}")
    return _PROMPTS_DIR / filename


def get_user_message(role: str, bead_id: str, base: str, stage: str, labels: list[str] | None = None) -> str:
    if not base and role not in ("investigator",):
        return _NO_BRANCH_ERROR
    parts = [f"Bead: {bead_id}"]
    if base:
        parts.append(f"Base branch: {base}")
    if labels:
        parts.append(f"Labels: {', '.join(labels)}")
    docs_path = get_config().get("docs_path")
    if docs_path:
        focus = _ROLE_DOC_FOCUS.get(role, "")
        parts.append(f"Documentation: {docs_path}" + (f" (focus: {focus})" if focus else ""))
    return "\n".join(parts)


def get_conductor_prompt_file() -> Path:
    return _PROMPTS_DIR / "conductor.md"


def get_conductor_user_message(requirement: str | None = None) -> str:
    return requirement or "Begin."
```

**Step 2: Verify the old `get_prompt` callers**

Check all imports of `get_prompt` and `get_conductor_prompt`:
- `src/debussy/spawner.py` — uses `get_prompt`
- `src/debussy/tmux.py` — uses `get_conductor_prompt`

**Step 3: Commit**

```bash
git add src/debussy/prompts/__init__.py
git commit -m "refactor prompts/__init__.py to return file paths and user messages"
```

---

### Task 3: Update `spawner.py`

**Files:**
- Modify: `src/debussy/spawner.py`

**Step 1: Update imports**

```python
from .prompts import get_prompt_file, get_user_message
```

**Step 2: Update `spawn_agent()` to get file + message**

Replace the single `prompt = get_prompt(...)` call with:

```python
prompt_file = get_prompt_file(role, stage)
user_message = get_user_message(role, bead_id, stage, stage, labels=labels)
```

And pass both to the spawn helpers.

**Step 3: Update `_spawn_tmux()`**

Change signature: `_spawn_tmux(agent_name, bead_id, role, prompt_file, user_message, stage, worktree_path="")`

Replace:
```python
cli_cmd += f" {shlex.quote(prompt)}"
```
With:
```python
cli_cmd += f" --system-prompt-file {shlex.quote(str(prompt_file))} {shlex.quote(user_message)}"
```

**Step 4: Update `_spawn_background()`**

Change signature: `_spawn_background(agent_name, bead_id, role, prompt_file, user_message, stage, worktree_path="")`

Replace:
```python
cmd.extend(["--print", prompt])
```
With:
```python
cmd.extend(["--system-prompt-file", str(prompt_file), "--print", user_message])
```

**Step 5: Update `spawn_agent()` call sites**

Update both `_spawn_tmux(...)` and `_spawn_background(...)` calls in `spawn_agent()` to pass `prompt_file` and `user_message` instead of `prompt`.

Also fix the `get_user_message` call — the current `get_user_message` signature is `(role, bead_id, base, stage, labels)`, so:

```python
base = get_base_branch()  # import this
prompt_file = get_prompt_file(role, stage)
user_message = get_user_message(role, bead_id, base, stage, labels=labels)
```

**Step 6: Commit**

```bash
git add src/debussy/spawner.py
git commit -m "update spawner to use --system-prompt-file"
```

---

### Task 4: Update `tmux.py` (conductor spawning)

**Files:**
- Modify: `src/debussy/tmux.py`

**Step 1: Update imports**

```python
from .prompts import get_conductor_prompt_file, get_conductor_user_message
```

**Step 2: Update `create_tmux_layout()`**

Replace:
```python
prompt = get_conductor_prompt()
if requirement:
    prompt = f"{prompt}\n\nUser requirement: {requirement}"
claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
claude_cmd += f" {shlex.quote(prompt)}"
```
With:
```python
prompt_file = get_conductor_prompt_file()
user_message = get_conductor_user_message(requirement)
claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
claude_cmd += f" --system-prompt-file {shlex.quote(str(prompt_file))} {shlex.quote(user_message)}"
```

**Step 3: Commit**

```bash
git add src/debussy/tmux.py
git commit -m "update conductor to use --system-prompt-file"
```

---

### Task 5: Delete old Python prompt modules

**Files:**
- Delete: `src/debussy/prompts/conductor.py`
- Delete: `src/debussy/prompts/developer.py`
- Delete: `src/debussy/prompts/reviewer.py`
- Delete: `src/debussy/prompts/security_reviewer.py`
- Delete: `src/debussy/prompts/integrator.py`
- Delete: `src/debussy/prompts/tester.py`
- Delete: `src/debussy/prompts/investigator.py`

**Step 1: Delete the files**

```bash
rm src/debussy/prompts/conductor.py
rm src/debussy/prompts/developer.py
rm src/debussy/prompts/reviewer.py
rm src/debussy/prompts/security_reviewer.py
rm src/debussy/prompts/integrator.py
rm src/debussy/prompts/tester.py
rm src/debussy/prompts/investigator.py
```

**Step 2: Verify nothing is broken**

```bash
python -c "from debussy.prompts import get_prompt_file, get_user_message, get_conductor_prompt_file, get_conductor_user_message; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add -A src/debussy/prompts/
git commit -m "remove old Python prompt modules"
```
