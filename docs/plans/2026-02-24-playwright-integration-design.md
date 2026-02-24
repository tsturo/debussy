# Playwright Integration Design

## Goal

Enable debussy agents to visually verify frontend work using Playwright. Developers self-verify UI with screenshots, write Playwright tests as artifacts, and acceptance runs them as part of the full suite.

## Approach: Label-Conditional Prompt

The `frontend` label (applied by conductor) triggers extended Playwright instructions in the developer prompt. No new pipeline stages, roles, or config keys.

Follows the same pattern as the existing `security` label.

## Prerequisite

Playwright CLI and browsers must be pre-installed on the machine (`npx playwright install`).

## How It Works

### Conductor

- Adds `frontend` label to beads involving UI work
- Includes the dev server command in the bead description (e.g., "Dev server: npm run dev (port 3000)")

### Developer (frontend beads)

When a bead has the `frontend` label, the developer prompt appends:

1. Parse the dev server command from the bead description
2. Start the dev server in the background
3. Wait for it to be ready (poll the port)
4. Use Playwright to navigate to the relevant page(s)
5. Take screenshots
6. Evaluate screenshots against the bead description
7. If something looks wrong, fix and repeat from step 4
8. Write Playwright test file(s) codifying the visual/functional checks
9. Run the Playwright tests to verify they pass
10. Kill the dev server
11. Continue with normal commit/push flow

### Reviewer

No changes. Code review only.

### Tester (acceptance)

After running the existing test suite, also runs Playwright tests if `playwright.config.{ts,js}` exists:

```
npx playwright test
```

## Plumbing

Labels flow from the watcher through the spawn chain:

```
watcher (has bead data with labels)
  → spawn_agent(role, bead_id, stage, labels)
    → get_prompt(role, bead_id, stage, labels)
      → developer_prompt(bead_id, base, labels)
```

Other prompt functions ignore the extra parameter.

## Files Changed

| File | Change |
|------|--------|
| `prompts/developer.py` | Accept labels, append Playwright block when `frontend` present |
| `prompts/tester.py` | Add Playwright test discovery step |
| `prompts/conductor.py` | Document `frontend` label usage and dev server in description |
| `prompts/__init__.py` | Pass labels to developer builder |
| `spawner.py` | Pass labels from bead data through to `get_prompt()` |
| `CLAUDE.md` | Document `frontend` label in pipeline docs |

## What Doesn't Change

- No new stages
- No new roles
- No new config keys
- No transition logic changes
- Pipeline flow is identical
