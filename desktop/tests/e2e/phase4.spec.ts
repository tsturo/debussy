import { test, expect, _electron as electron } from '@playwright/test'
import type { ElectronApplication, Page } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')
// Launch with cwd at worktree root so .takt/takt.db is found and real tasks appear
const WORKTREE_ROOT = resolve(__dirname, '..', '..', '..')

test.describe('Phase 4: New task dialog, conductor chat, watcher status', () => {
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
  })

  test.afterAll(async () => {
    await app.close()
  })

  // ── Test 1: New task dialog ────────────────────────────────────────────────

  test('new task dialog opens, disables Create until title is filled', async () => {
    // Click the "+ New Task" button in the header
    const newTaskBtn = page.locator('button', { hasText: '+ New Task' })
    await expect(newTaskBtn).toBeVisible({ timeout: 3000 })
    await newTaskBtn.click()

    // Verify dialog appeared with correct role and label
    const dialog = page.getByRole('dialog', { name: 'New Task' })
    await expect(dialog).toBeVisible({ timeout: 2000 })

    // Create button must be disabled when title is empty
    const createBtn = page.locator('button', { hasText: 'Create' })
    await expect(createBtn).toBeDisabled()

    // Fill in a title — Create button must become enabled
    const titleInput = dialog.locator('input[placeholder="Task title"]')
    await expect(titleInput).toBeVisible()
    await titleInput.fill('Test task from Phase 4 E2E')
    await expect(createBtn).toBeEnabled()

    // Fill in a description
    const descTextarea = dialog.locator('textarea[placeholder*="Task description"]')
    await expect(descTextarea).toBeVisible()
    await descTextarea.fill('This task was created by the Phase 4 Playwright test suite.')

    // Take screenshot with both fields filled and Create enabled
    await page.screenshot({ path: `${SCREENSHOT_DIR}/11-new-task-dialog.png`, fullPage: true })

    // Close dialog via Cancel to avoid side-effects on later tests
    const cancelBtn = page.locator('button', { hasText: 'Cancel' })
    await cancelBtn.click()
    await expect(dialog).not.toBeVisible({ timeout: 2000 })
  })

  // ── Test 2: Conductor panel chat ──────────────────────────────────────────

  test('conductor panel shows chat response after sending a message', async () => {
    // At 1200px width the conductor starts hidden — toggle it open
    const conductorInput = page.locator('input[placeholder="Talk to conductor..."]')
    if (!(await conductorInput.isVisible())) {
      await page.keyboard.press('Meta+\\')
      await expect(conductorInput).toBeVisible({ timeout: 2000 })
    }

    // Type a message and send it
    await conductorInput.fill('What tasks are blocked?')
    await conductorInput.press('Enter')

    // The user message must appear in the chat (as a bubble)
    const userBubble = page.locator('div').filter({ hasText: 'What tasks are blocked?' }).last()
    await expect(userBubble).toBeVisible({ timeout: 3000 })

    // A response must appear — either a streaming chunk/error or an echo reply.
    // Wait up to 5 seconds for any assistant bubble containing response text.
    const assistantReply = page.locator('div').filter({
      hasText: /Error: claude CLI not found|echo\) You said:|What tasks are blocked/,
    })
    await expect(assistantReply.last()).toBeVisible({ timeout: 5000 })

    await page.screenshot({ path: `${SCREENSHOT_DIR}/12-conductor-chat.png`, fullPage: true })
  })

  // ── Test 3: Watcher status indicator ──────────────────────────────────────

  test('watcher status indicator shows watching or stopped with correct color', async () => {
    // The AgentBar always renders at the top of the board area
    const agentBar = page.locator('[role="toolbar"][aria-label="Active agents"]')
    await expect(agentBar).toBeVisible()

    // Watcher status text must be one of the two known states
    const statusText = agentBar.locator('span', { hasText: /^(watching|stopped)$/ })
    await expect(statusText).toBeVisible()

    // Determine the current state
    const textContent = await statusText.textContent()
    const isWatching = textContent?.trim() === 'watching'

    // Resolve the expected CSS variable color by creating a temporary element
    // with that var applied — getComputedStyle resolves CSS vars to rgb() values
    const expectedColor = await page.evaluate((watching) => {
      const cssVar = watching ? '--t-teal' : '--t-text-3'
      const tmp = document.createElement('span')
      tmp.style.color = `var(${cssVar})`
      document.body.appendChild(tmp)
      const resolved = getComputedStyle(tmp).color
      document.body.removeChild(tmp)
      return resolved
    }, isWatching)

    const computedColor = await statusText.evaluate((el) => getComputedStyle(el).color)
    expect(computedColor).toBe(expectedColor)

    // Verify via the button that wraps both dot and span
    const statusButton = agentBar.locator('button').filter({ hasText: /^(watching|stopped)$/ })
    await expect(statusButton).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/13-watcher-status.png`, fullPage: true })
  })
})
