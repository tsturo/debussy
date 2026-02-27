def _frontend_block(bead_id: str) -> str:
    return f"""

FRONTEND VISUAL VERIFICATION (this bead has the `frontend` label):

Before committing, perform visual verification:

A) START DEV SERVER:
   - Read the bead description for the dev server command (e.g., "Dev server: npm run dev (port 3000)")
   - If no dev server command is in the description:
     bd comment {bead_id} "Blocked: no dev server command in bead description"
     bd update {bead_id} --status blocked
     Exit immediately.
   - Start it in the background: <command> &
   - Wait for it to be ready: poll the URL until it responds (max 30 seconds)

B) VISUAL VERIFICATION LOOP (use Playwright MCP):
   - browser_navigate to the relevant page URL
   - browser_take_screenshot to capture the current state
   - Evaluate the screenshot against the bead description
   - Use browser_click, browser_fill_form, browser_hover to test interactions
   - If it looks wrong or incomplete, fix the code and repeat
   - Max 3 iterations — if still broken after 3, commit what you have and note issues in a comment

C) WRITE PLAYWRIGHT TESTS:
   - Create Playwright test file(s) that codify the visual/functional checks you just verified
   - Tests should cover: page loads, key elements visible, interactions work as described
   - Run: npx playwright test <your-test-file>
   - Fix until tests pass

D) CLEANUP:
   - browser_close to close the Playwright browser
   - Kill the dev server process

SKILLS:
   - Invoke /frontend-design before implementing any UI work
   - Use Playwright MCP tools (browser_navigate, browser_take_screenshot, browser_click, browser_fill_form) for all visual verification — do NOT use npx playwright screenshot"""


def developer_prompt(bead_id: str, base: str, labels: list[str] | None = None) -> str:
    frontend_section = _frontend_block(bead_id) if labels and "frontend" in labels else ""
    return f"""You are an autonomous developer agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Do NOT say "Would you like me to..." or similar. Just do the work.

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

START NOW. Do not wait for instructions. Begin with step 1."""
