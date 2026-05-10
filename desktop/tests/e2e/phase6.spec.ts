import { test, expect, _electron as electron } from '@playwright/test'
import type { ElectronApplication, Page } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')
// Launch with cwd at worktree root so .takt/takt.db is found and real tasks appear
const WORKTREE_ROOT = resolve(__dirname, '..', '..', '..')

test.describe('Phase 6: Dense board, status strip counts, conductor session', () => {
  let app: ElectronApplication
  let page: Page

  test.beforeAll(async () => {
    mkdirSync(SCREENSHOT_DIR, { recursive: true })
    app = await electron.launch({
      args: [APP_MAIN],
      cwd: WORKTREE_ROOT,
    })
    page = await app.firstWindow()
    await page.waitForLoadState('domcontentloaded')
    // Allow initial IPC data fetch to complete
    await page.waitForTimeout(800)

    // Switch active project to WORKTREE_ROOT so real tasks are loaded.
    // When Playwright uses Electron's generic userData dir the saved workspace
    // may point to a different path that has no tasks.
    const workspace = await page.evaluate(() => window.debussy.workspace.list())
    const groupId = workspace.groups[0]?.id
    if (groupId && workspace.activeProjectPath !== WORKTREE_ROOT) {
      // Add project if not already present (ignore "already added" error)
      await page.evaluate(
        async ([gid, path]) => {
          await window.debussy.workspace.addProject(gid, path)
        },
        [groupId, WORKTREE_ROOT],
      )
      await page.evaluate(
        async ([gid, path]) => {
          await window.debussy.workspace.setActive(gid, path)
        },
        [groupId, WORKTREE_ROOT],
      )
      // Wait for fetchAll to complete after project switch
      await page.waitForTimeout(800)
    }
  })

  test.afterAll(async () => {
    await app.close()
  })

  // ── Test 1: Dense board ────────────────────────────────────────────────────

  test('board shows tasks in compact card layout', async () => {
    // AgentBar is always rendered at the top of the board area
    const agentBar = page.locator('[role="toolbar"][aria-label="Active agents"]')
    await expect(agentBar).toBeVisible({ timeout: 3000 })

    // Wait for tasks to load — kanban cards use role="button" on a div
    // KanbanCard renders: <div role="button" ... style={{minHeight: '36px'}}>
    const kanbanCards = page.locator('[role="button"]').filter({
      has: page.locator('span').filter({ hasText: /^DBS-/ }),
    })
    await expect(kanbanCards.first()).toBeVisible({ timeout: 5000 })

    const cardCount = await kanbanCards.count()
    expect(cardCount).toBeGreaterThanOrEqual(1)

    // Compact layout: cards are approximately 36px tall (DBS-55: minHeight 36px)
    const firstCardBox = await kanbanCards.first().boundingBox()
    expect(firstCardBox).not.toBeNull()
    if (firstCardBox) {
      // Cards may be slightly taller with content, but should remain compact (≤ 50px)
      expect(firstCardBox.height).toBeLessThanOrEqual(50)
    }

    // Take the required dense-board screenshot
    await page.screenshot({ path: `${SCREENSHOT_DIR}/15-dense-board.png`, fullPage: true })
  })

  // ── Test 2: Status strip stage counts ─────────────────────────────────────

  test('status strip shows per-stage task counts when tasks exist', async () => {
    // Dismiss any selected task so the collapsed strip is shown
    await page.keyboard.press('Escape')

    // CollapsedStrip renders at the bottom of the main area when no task is
    // selected.  Its center div shows "N dev · M review · K merge · J done"
    // when tasks exist in those stages (STRIP_STAGES in TaskDetailShell.tsx).
    // With real .takt data there will be tasks in at least the "done" stage.
    const stripCountText = page.locator('div').filter({
      hasText: /\d+ (dev|review|merge|done)/,
    })
    await expect(stripCountText.last()).toBeVisible({ timeout: 3000 })

    const text = await stripCountText.last().textContent()
    // Must contain at least one stage count (e.g. "56 done")
    expect(text).toMatch(/\d+ (dev|review|merge|done)/)

    // Must NOT be the fallback "0 agents" shown when there are no tasks
    expect(text).not.toMatch(/^0 agents/)
  })

  // ── Test 3: Conductor session ID in config ─────────────────────────────────

  test('conductor session ID is persisted in config after first message send', async () => {
    // Open the conductor panel if hidden (Cmd+\ toggles it)
    const conductorInput = page.locator('input[placeholder="Talk to conductor..."]')
    if (!(await conductorInput.isVisible())) {
      await page.keyboard.press('Meta+\\')
      await expect(conductorInput).toBeVisible({ timeout: 2000 })
    }

    // Send a message — this triggers ConductorBridge.sendMessage → getOrCreateSessionId
    // which writes conductor_session_id to .debussy/config.json
    await conductorInput.fill('ping')
    await conductorInput.press('Enter')

    // User bubble must appear to confirm the message was submitted
    const userBubble = page.locator('div').filter({ hasText: 'ping' }).last()
    await expect(userBubble).toBeVisible({ timeout: 3000 })

    // Allow time for the IPC round-trip and file write
    await page.waitForTimeout(500)

    // Read config via the IPC API exposed to the renderer
    const config = await page.evaluate(() => window.debussy.config.get())

    expect(config.conductor_session_id).toBeTruthy()
    expect(typeof config.conductor_session_id).toBe('string')

    // A valid UUID has the form xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    expect(config.conductor_session_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    )
  })

  // ── Test 4: New Session button clears the chat ─────────────────────────────

  test('clicking New Session button clears the conductor chat', async () => {
    // Conductor panel must be open — it was opened in the previous test
    const conductorInput = page.locator('input[placeholder="Talk to conductor..."]')
    if (!(await conductorInput.isVisible())) {
      await page.keyboard.press('Meta+\\')
      await expect(conductorInput).toBeVisible({ timeout: 2000 })
    }

    // Send a distinct message so we have a visible user bubble to check
    const testMessage = 'Phase 6 New Session test message'
    await conductorInput.fill(testMessage)
    await conductorInput.press('Enter')

    // Confirm the message appears in the chat
    const sentBubble = page.locator('div').filter({ hasText: testMessage }).last()
    await expect(sentBubble).toBeVisible({ timeout: 3000 })

    // Click the "New Session" button (aria-label="New session" on the icon button
    // in the Conductor header — calls clearConductorMessages + conductor.newSession)
    const newSessionBtn = page.getByRole('button', { name: 'New session' })
    await expect(newSessionBtn).toBeVisible({ timeout: 2000 })
    await newSessionBtn.click()

    // After clearing, the user bubble we just sent must no longer be visible
    await expect(sentBubble).not.toBeVisible({ timeout: 2000 })
  })
})
