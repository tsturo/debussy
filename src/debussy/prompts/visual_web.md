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
