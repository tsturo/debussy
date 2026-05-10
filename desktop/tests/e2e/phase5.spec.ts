import { test, expect, _electron as electron } from '@playwright/test'
import type { ElectronApplication, Page } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')
// Launch with cwd at worktree root so .takt/takt.db is found and real tasks appear
const WORKTREE_ROOT = resolve(__dirname, '..', '..', '..')

test.describe('Phase 5: Workspace management and theme card visuals', () => {
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

  // ── Test 1: Workspace switcher opens ─────────────────────────────────────────

  test('workspace switcher opens when workspace area in sidebar is clicked', async () => {
    // Sidebar starts collapsed — expand it first
    const expandBtn = page.getByRole('button', { name: 'Expand sidebar' }).first()
    await expect(expandBtn).toBeVisible({ timeout: 2000 })
    await expandBtn.click()

    // "Projects" section label confirms the sidebar is expanded
    await expect(page.getByText('Projects', { exact: true }).first()).toBeVisible({ timeout: 2000 })

    // Click the workspace header button (top of sidebar, shows workspace name + chevron)
    const switchBtn = page.getByRole('button', { name: 'Switch workspace' })
    await expect(switchBtn).toBeVisible({ timeout: 2000 })
    await switchBtn.click()

    // The workspace dropdown must appear — it always contains a "New Workspace" option
    const newWorkspaceBtn = page.locator('button', { hasText: 'New Workspace' })
    await expect(newWorkspaceBtn).toBeVisible({ timeout: 2000 })

    await page.screenshot({ path: `${SCREENSHOT_DIR}/14a-workspace-dropdown.png`, fullPage: true })

    // Close the dropdown via Escape
    await page.keyboard.press('Escape')
    await expect(newWorkspaceBtn).not.toBeVisible({ timeout: 2000 })
  })

  // ── Test 2: Project list from real data ──────────────────────────────────────

  test('sidebar shows at least one project from real workspace data', async () => {
    // Sidebar should still be expanded from test 1
    await expect(page.getByText('Projects', { exact: true }).first()).toBeVisible({ timeout: 2000 })

    // Project row buttons have no SVG children (unlike Add project / Settings / workspace buttons).
    // This reliably distinguishes them from all other sidebar buttons.
    const projectRowBtns = page.locator('button').filter({
      has: page.locator('span'),
      hasNot: page.locator('svg'),
    })

    // At least one project must be present — workspace-store always creates a default
    // group with the cwd as its first project when no saved data exists.
    const count = await projectRowBtns.count()
    expect(count).toBeGreaterThanOrEqual(1)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/14b-sidebar-projects.png`, fullPage: true })
  })

  // ── Test 3: Theme cards are visually distinguishable ─────────────────────────

  test('theme cards in settings look visually different from each other', async () => {
    // Open settings modal
    await page.keyboard.press('Meta+,')
    const settings = page.getByRole('dialog', { name: 'Settings' })
    await expect(settings).toBeVisible({ timeout: 2000 })

    // All three theme cards must be present
    const themeCards = page.locator('button[aria-pressed]').filter({ hasText: /^(System|Dark|Light)$/ })
    await expect(themeCards).toHaveCount(3)

    const darkCard = themeCards.filter({ hasText: 'Dark' })
    const lightCard = themeCards.filter({ hasText: 'Light' })
    const systemCard = themeCards.filter({ hasText: 'System' })

    await expect(darkCard).toBeVisible()
    await expect(lightCard).toBeVisible()
    await expect(systemCard).toBeVisible()

    // Each ThemeSwatch renders a div[aria-hidden="true"] with a visually distinct appearance.
    // Dark swatch:   background '#0a0f1a'  → rgb(10, 15, 26)
    // Light swatch:  background '#f7f7fb'  → rgb(247, 247, 251)
    // System swatch: two child halves — left dark, right light
    const darkSwatchBg = await darkCard.locator('[aria-hidden="true"]').evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    const lightSwatchBg = await lightCard.locator('[aria-hidden="true"]').evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )

    // Dark and light swatches must have different background colours
    expect(darkSwatchBg).not.toBe(lightSwatchBg)

    // Dark swatch must use a dark background (R component of rgb(10, 15, 26) is 10)
    expect(darkSwatchBg).toMatch(/^rgb\(10,/)

    // Light swatch must use a light background (R component of rgb(247, 247, 251) is 247)
    expect(lightSwatchBg).toMatch(/^rgb\(247,/)

    // System card swatch renders two child divs (left = dark half, right = light half)
    const systemSwatchChildren = systemCard.locator('[aria-hidden="true"] > div')
    await expect(systemSwatchChildren).toHaveCount(2)

    const systemLeftBg = await systemSwatchChildren.nth(0).evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    const systemRightBg = await systemSwatchChildren.nth(1).evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )

    // The two halves of the system card must have different backgrounds
    expect(systemLeftBg).not.toBe(systemRightBg)

    // Capture the required screenshot of all three theme cards
    await page.screenshot({ path: `${SCREENSHOT_DIR}/14-theme-cards.png`, fullPage: true })

    // Close settings
    await page.keyboard.press('Escape')
    await expect(settings).not.toBeVisible({ timeout: 2000 })
  })
})
