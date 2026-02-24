# Playwright Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable debussy developer agents to visually verify frontend work using Playwright, and acceptance testers to run Playwright tests as part of the full suite.

**Architecture:** The `frontend` label (set by conductor) triggers extended Playwright instructions in the developer prompt. Labels are plumbed from the watcher through spawn_agent → get_prompt → developer_prompt. No new stages, roles, or pipeline changes.

**Tech Stack:** Python, Playwright CLI (npx playwright)

---

### Task 1: Plumb labels through spawn chain

Three files need coordinated changes to pass bead labels from the watcher to prompt builders.

**Files:**
- Modify: `src/debussy/spawner.py:153` (spawn_agent signature)
- Modify: `src/debussy/spawner.py:169` (get_prompt call)
- Modify: `src/debussy/prompts/__init__.py:21-27` (builder lambdas)
- Modify: `src/debussy/prompts/__init__.py:30` (get_prompt signature)
- Modify: `src/debussy/pipeline_checker.py:217` (spawn_agent call)

**Step 1: Update `spawn_agent` in `spawner.py`**

Add `labels` parameter and pass it to `get_prompt`:

```python
def spawn_agent(watcher, role: str, bead_id: str, stage: str, labels: list[str] | None = None) -> bool:
```

Change line 169 from:
```python
    prompt = get_prompt(role, bead_id, stage)
```
to:
```python
    prompt = get_prompt(role, bead_id, stage, labels=labels)
```

**Step 2: Update `get_prompt` in `prompts/__init__.py`**

Change signature and builder dict to accept labels:

```python
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
```

**Step 3: Update `_scan_stage` in `pipeline_checker.py`**

Pass labels from bead data to `spawn_agent`. Change line 217 from:
```python
        if spawn_agent(watcher, role, bead_id, stage):
```
to:
```python
        if spawn_agent(watcher, role, bead_id, stage, labels=bead.get("labels")):
```

**Step 4: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All existing tests pass (labels parameter is optional with default None).

**Step 5: Commit**

```bash
git add src/debussy/spawner.py src/debussy/prompts/__init__.py src/debussy/pipeline_checker.py
git commit -m "[playwright] Plumb bead labels through spawn chain to prompt builders"
```

---

### Task 2: Add Playwright block to developer prompt

**Files:**
- Modify: `src/debussy/prompts/developer.py`

**Step 1: Add frontend visual verification block**

Change the function signature and append Playwright instructions when `frontend` label is present:

```python
def _frontend_block(bead_id: str) -> str:
    return f"""

FRONTEND VISUAL VERIFICATION (this bead has the `frontend` label):

After implementing the feature and before committing:

A) START DEV SERVER:
   - Read the bead description for the dev server command (e.g., "Dev server: npm run dev (port 3000)")
   - Start it in the background: <command> &
   - Wait for it to be ready: poll the URL until it responds (max 30 seconds)
   - If no dev server command is in the description, set blocked: bd comment {bead_id} "Blocked: no dev server command in bead description"

B) VISUAL VERIFICATION LOOP:
   - Use Playwright to navigate to the relevant page(s)
   - Take a screenshot: npx playwright screenshot --wait-for-timeout 2000 <url> screenshot.png
   - Read the screenshot file to visually evaluate it
   - Compare what you see against the bead description
   - If it looks wrong or incomplete, fix the code and repeat this loop
   - Max 3 iterations — if still broken after 3, commit what you have and note issues in a comment

C) WRITE PLAYWRIGHT TESTS:
   - Create Playwright test file(s) that codify the visual/functional checks you just verified
   - Tests should cover: page loads, key elements visible, interactions work as described
   - Run: npx playwright test <your-test-file>
   - Fix until tests pass

D) CLEANUP:
   - Kill the dev server process
   - Include Playwright test files in your commit"""


def developer_prompt(bead_id: str, base: str, labels: list[str] | None = None) -> str:
    frontend_section = _frontend_block(bead_id) if labels and "frontend" in labels else ""
    return f\"\"\"You are an autonomous developer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Do NOT say "Would you like me to..." or similar. Just do the work.

Bead: {bead_id}
Base branch: {base}

EXECUTE THESE STEPS NOW:

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git pull origin {base}
4. VERIFY: run `git branch --show-current` — must show `feature/{bead_id}`. If not, STOP and set status blocked.
5. Implement the task — keep functions small and testable
6. If the bead description includes test criteria, write tests covering ALL of them. If no test criteria are specified, skip tests.
7. Run tests to verify they pass{frontend_section}
8. SCOPE CHECK: run `git diff origin/{base}...HEAD --stat` — every changed file must be relevant to the bead description. Do NOT modify or delete files/tests that belong to other beads.
9. Commit and push changes
10. bd update {bead_id} --status open
11. Exit

IMPORTANT: You are already on branch feature/{bead_id}. Do NOT checkout other branches.

IF TASK IS TOO BIG (needs 3+ files, multiple behaviors, or you can't finish in one session):
  bd comment {bead_id} "Too big — suggest splitting: 1) [subtask A] 2) [subtask B] ..."
  bd update {bead_id} --status blocked
  Exit. Let conductor split it.

IF BLOCKED — dependencies missing, code you need doesn't exist yet, or requirements unclear:
  bd comment {bead_id} "Blocked: [reason — what is missing or unclear]"
  bd update {bead_id} --status blocked
  Exit immediately. Do NOT set status open with no commits.

IF YOU FIND AN UNRELATED BUG:
  bd comment {bead_id} "Unrelated bug: [title] — [details]"
  Continue with your task. The conductor will triage it.

START NOW. Do not wait for instructions. Begin with step 1.\"\"\"
```

**Step 2: Run tests**

Run: `python -m pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/debussy/prompts/developer.py
git commit -m "[playwright] Add Playwright visual verification block to developer prompt"
```

---

### Task 3: Add Playwright test discovery to tester prompt

**Files:**
- Modify: `src/debussy/prompts/tester.py`

**Step 1: Add Playwright step to acceptance prompt**

In `_batch_acceptance_prompt`, add step 5 for Playwright test discovery between existing step 4 and the RESULTS section:

After the line `   - Run all discovered tests`, add:
```
5. If playwright.config.ts or playwright.config.js exists:
   - Start the dev server if package.json has a "dev" or "start" script: npm run dev &
   - Wait for it to be ready (poll localhost, max 30 seconds)
   - Run: npx playwright test
   - Kill the dev server
   - Include Playwright results in pass/fail determination
```

And renumber existing step 5 to step 6.

**Step 2: Run tests**

Run: `python -m pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/debussy/prompts/tester.py
git commit -m "[playwright] Add Playwright test discovery to acceptance tester prompt"
```

---

### Task 4: Document frontend label in conductor prompt

**Files:**
- Modify: `src/debussy/prompts/conductor.py`

**Step 1: Add FRONTEND LABEL section after the SECURITY LABEL section**

After the SECURITY LABEL block (after the `Example: bd update <id> --add-label security` line), add:

```
FRONTEND LABEL — add `frontend` to beads that involve UI/visual work. This triggers Playwright
visual verification during development. The developer will start a dev server, take screenshots,
and write Playwright tests. Apply it when the task involves:
- Creating or modifying UI components, pages, or layouts
- Visual styling or responsive design changes
- Interactive elements (forms, modals, navigation)
IMPORTANT: Always include the dev server command in the bead description.
Example: bd create "Build login form" -d "Create LoginForm component in src/components/LoginForm.tsx. Dev server: npm run dev (port 3000)"
Example: bd update <id> --add-label frontend
A bead can have both `security` and `frontend` labels.
```

**Step 2: Commit**

```bash
git add src/debussy/prompts/conductor.py
git commit -m "[playwright] Document frontend label in conductor prompt"
```

---

### Task 5: Document frontend label in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add frontend label to Pipeline Flow section**

After the line about `security` label in the Pipeline Flow section, add:

```
Beads with the `frontend` label (set by conductor) trigger Playwright visual verification during development. The developer starts a dev server, takes screenshots, verifies visually, and writes Playwright tests.
```

**Step 2: Add frontend label to the Agents section under @developer**

Update the @developer section to mention:
```
- For `frontend` beads: starts dev server, verifies UI visually with Playwright screenshots, writes Playwright tests
```

**Step 3: Add prerequisite note**

In the Commands section or a new Prerequisites section, add:
```
For frontend visual testing: `npx playwright install` (pre-install Playwright browsers)
```

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "[playwright] Document frontend label and Playwright workflow in CLAUDE.md"
```

---

## Parallelization

Tasks can be split across a team:

| Agent | Tasks | Files |
|-------|-------|-------|
| Agent A | Task 1 (plumbing) | spawner.py, prompts/__init__.py, pipeline_checker.py |
| Agent B | Task 2 (developer prompt) | prompts/developer.py |
| Agent C | Task 3 + Task 4 + Task 5 (tester, conductor, docs) | prompts/tester.py, prompts/conductor.py, CLAUDE.md |

All three agents work on different files — no merge conflicts.

Task 1 must be committed first (other tasks depend on the new `labels` parameter in `developer_prompt`), but since each agent touches different files, they can all work in parallel and commits can be ordered during integration.
