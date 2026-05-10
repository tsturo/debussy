import { test, expect, _electron as electron } from '@playwright/test'
import type { ElectronApplication, Page } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')
// Launch with cwd at worktree root so .takt/takt.db is found and tasks appear
const WORKTREE_ROOT = resolve(__dirname, '..', '..', '..')

// ── Shared-app tests (need real task data) ────────────────────────────────────

test.describe('Coverage: with real task database', () => {
  let app: ElectronApplication
  let page: Page

  test.beforeAll(async () => {
    mkdirSync(SCREENSHOT_DIR, { recursive: true })
    app = await electron.launch({ args: [APP_MAIN], cwd: WORKTREE_ROOT })
    page = await app.firstWindow()
    await page.waitForLoadState('domcontentloaded')
    // Allow initial IPC data fetch to complete
    await page.waitForTimeout(800)
  })

  test.afterAll(async () => {
    await app.close()
  })

  test('sidebar expand/collapse shows and hides project list', async () => {
    // At the default viewport (< 1920px) the sidebar starts collapsed.
    // Two buttons carry aria-label "Expand sidebar" (sidebar header + strip toggle);
    // use first() to avoid strict-mode violation — both trigger the same action.
    const expandBtn = page.getByRole('button', { name: 'Expand sidebar' }).first()
    await expect(expandBtn).toBeVisible({ timeout: 2000 })

    // Click to expand — the "Projects" section label should appear
    await expandBtn.click()
    await expect(page.getByText('Projects', { exact: true })).toBeVisible({ timeout: 2000 })
    await page.screenshot({ path: `${SCREENSHOT_DIR}/08-sidebar-expanded.png`, fullPage: true })

    // Click to collapse — project list should disappear
    const collapseBtn = page.getByRole('button', { name: 'Collapse sidebar' })
    await collapseBtn.click()
    await expect(page.getByText('Projects', { exact: true })).not.toBeVisible({ timeout: 2000 })
  })

  test('task card stage colors have a colored left border', async () => {
    // At least one task card exists given the real database
    const firstCard = page.locator('[role="button"]').first()
    await expect(firstCard).toBeVisible({ timeout: 3000 })

    // KanbanCard sets borderLeft inline style: "<n>px solid <color>".
    // Browsers normalise hex colours to rgb() when read back via .style.
    const borderLeft = await firstCard.evaluate(
      (el) => (el as HTMLElement).style.borderLeft,
    )
    // Matches both hex (#rrggbb) and normalised rgb(r, g, b) forms
    expect(borderLeft).toMatch(/\d+px solid (rgb\(\d+,\s*\d+,\s*\d+\)|#[0-9a-fA-F]{6})/)
  })

  test('task detail body shows description section and comment input', async () => {
    const firstCard = page.locator('[role="button"]').first()
    await expect(firstCard).toBeVisible({ timeout: 3000 })
    await firstCard.click()

    // Verify detail panel expanded (Advance + Block buttons are present)
    await expect(page.locator('button', { hasText: 'Advance' })).toBeVisible({ timeout: 2000 })

    // Description section label must be visible inside the body
    await expect(page.getByText('Description', { exact: true })).toBeVisible()

    // Comment input must be visible
    await expect(page.locator('input[placeholder="Add a comment..."]')).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/10-task-detail-body.png`, fullPage: true })

    // Reset for subsequent tests
    await page.keyboard.press('Escape')
  })
})

// ── Standalone tests (each launches its own app instance) ────────────────────

test('agent bar renders with watcher status even with zero agents', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  // Launch without WORKTREE_ROOT — no agent state loaded from disk
  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(800)

  // AgentBar must always be visible regardless of agent count
  const agentBar = page.locator('[role="toolbar"][aria-label="Active agents"]')
  await expect(agentBar).toBeVisible()

  // Watcher status indicator must show either "watching" or "stopped"
  const statusText = agentBar.locator('span', { hasText: /^(watching|stopped)$/ })
  await expect(statusText).toBeVisible()

  await app.close()
})

test('dark theme on launch shows dark background color', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  // Remove any saved preference to test the true default dark launch
  await page.evaluate(() => localStorage.removeItem('debussy-theme'))
  await page.reload()
  await page.waitForLoadState('domcontentloaded')

  // data-theme must resolve to 'dark' by default
  const theme = await page.evaluate(() =>
    document.documentElement.getAttribute('data-theme'),
  )
  expect(theme).toBe('dark')

  // The dark palette CSS variable --t-bg must be the expected dark value
  const bgVar = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--t-bg').trim(),
  )
  expect(bgVar).toBe('#0a0f1a')

  await page.screenshot({ path: `${SCREENSHOT_DIR}/09-dark-launch.png`, fullPage: true })

  await app.close()
})

test('empty board columns render even with zero tasks in each stage', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  // Launch without a real .takt database — IPC returns an empty task list
  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(800)

  // Core stage columns must be present even when their task count is 0
  await expect(page.getByText('DEV', { exact: true })).toBeVisible()
  await expect(page.getByText('REVIEW', { exact: true })).toBeVisible()
  await expect(page.getByText('MERGE', { exact: true })).toBeVisible()
  await expect(page.getByText('DONE', { exact: true })).toBeVisible()

  // Each empty column renders a count badge showing "0"
  // There will be multiple "0" badges — verifying at least one is sufficient
  await expect(page.getByText('0').first()).toBeVisible()

  await app.close()
})
