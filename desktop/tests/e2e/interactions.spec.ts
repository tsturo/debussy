import { test, expect, _electron as electron } from '@playwright/test'
import type { ElectronApplication, Page } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')
// Launch with cwd at worktree root so .takt/takt.db is found and mock tasks appear
const WORKTREE_ROOT = resolve(__dirname, '..', '..', '..')

test.describe('App interactions', () => {
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

  test('board renders with columns', async () => {
    await expect(page.locator('.app-shell')).toBeVisible()
    await expect(page.locator('header')).toBeVisible()
    // Verify at least the DEV and DONE stage columns are present (exact match on column labels)
    await expect(page.getByText('DEV', { exact: true })).toBeVisible()
    await expect(page.getByText('DONE', { exact: true })).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-board.png`, fullPage: true })
  })

  test('task selection shows detail panel', async () => {
    // Click the first visible task card on the board
    const firstCard = page.locator('[role="button"]').first()
    await expect(firstCard).toBeVisible({ timeout: 3000 })
    await firstCard.click()
    // Verify the task detail panel expanded (Advance + Block buttons appear)
    await expect(page.locator('button', { hasText: 'Advance' })).toBeVisible({ timeout: 2000 })
    await expect(page.locator('button', { hasText: 'Block' })).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-task-detail.png`, fullPage: true })
  })

  test('Escape closes task detail', async () => {
    // Panel is open from previous test; Escape should collapse it
    await page.keyboard.press('Escape')
    // Advance button disappears when panel collapses to the status strip
    await expect(page.locator('button', { hasText: 'Advance' })).not.toBeVisible({ timeout: 2000 })
  })

  test('conductor toggle shows and hides panel', async () => {
    // Use the conductor's message input as the visibility indicator — it only
    // exists when the panel is rendered (not a substring match on task titles).
    const conductorInput = page.locator('input[placeholder="Talk to conductor..."]')

    // At 1200px width, conductor starts hidden. First press shows it.
    await page.keyboard.press('Meta+\\')
    await expect(conductorInput).toBeVisible({ timeout: 2000 })

    // Second press hides it — take screenshot showing board without conductor
    await page.keyboard.press('Meta+\\')
    await expect(conductorInput).not.toBeVisible({ timeout: 2000 })
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-no-conductor.png`, fullPage: true })

    // Third press shows it again to confirm bidirectional toggle
    await page.keyboard.press('Meta+\\')
    await expect(conductorInput).toBeVisible({ timeout: 2000 })
  })

  test('command palette filters results and executes action', async () => {
    // Open command palette
    await page.keyboard.press('Meta+k')
    const palette = page.getByRole('dialog', { name: 'Command palette' })
    await expect(palette).toBeVisible({ timeout: 2000 })

    // Fill the palette input directly to avoid focus race with autofocus setTimeout
    const paletteInput = page.locator('input[placeholder="Type a command..."]')
    await paletteInput.fill('dark')

    // Verify filtered results show the dark theme action
    await expect(page.getByText('Switch to Dark Theme')).toBeVisible()

    // Take screenshot while palette is visible with filtered results
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-command-palette.png`, fullPage: true })

    // Press Enter to execute the highlighted action (Switch to Dark Theme)
    await paletteInput.press('Enter')
    await expect(palette).not.toBeVisible({ timeout: 2000 })

    // Verify dark theme is now active
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark', { timeout: 2000 })
  })

  test('settings modal opens with Cmd+Comma', async () => {
    await page.keyboard.press('Meta+,')
    const settings = page.getByRole('dialog', { name: 'Settings' })
    await expect(settings).toBeVisible({ timeout: 2000 })
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06-settings.png`, fullPage: true })
  })

  test('theme switch to light in settings', async () => {
    // Settings is open from the previous test; click the Light theme card
    const lightCard = page
      .locator('button[aria-pressed]')
      .filter({ hasText: 'Light' })
    await expect(lightCard).toBeVisible({ timeout: 2000 })
    await lightCard.click()

    // Verify the html[data-theme] attribute switched to light
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme'),
    )
    expect(theme).toBe('light')

    await page.screenshot({ path: `${SCREENSHOT_DIR}/07-light-theme.png`, fullPage: true })

    // Close settings via Escape
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: 'Settings' })).not.toBeVisible({
      timeout: 2000,
    })
  })

  test('only active theme card is selected (aria-pressed)', async () => {
    // Re-open settings
    await page.keyboard.press('Meta+,')
    const settings = page.getByRole('dialog', { name: 'Settings' })
    await expect(settings).toBeVisible({ timeout: 2000 })

    const themeCards = page.locator('button[aria-pressed]').filter({ hasText: /^(System|Dark|Light)$/ })

    // Click Dark card
    const darkCard = themeCards.filter({ hasText: 'Dark' })
    await darkCard.click()

    // Only Dark card should be pressed
    await expect(darkCard).toHaveAttribute('aria-pressed', 'true')
    await expect(themeCards.filter({ hasText: 'System' })).toHaveAttribute('aria-pressed', 'false')
    await expect(themeCards.filter({ hasText: 'Light' })).toHaveAttribute('aria-pressed', 'false')

    // Click Light card
    const lightCard = themeCards.filter({ hasText: 'Light' })
    await lightCard.click()

    // Only Light card should be pressed; Dark and System should not be
    await expect(lightCard).toHaveAttribute('aria-pressed', 'true')
    await expect(darkCard).toHaveAttribute('aria-pressed', 'false')
    await expect(themeCards.filter({ hasText: 'System' })).toHaveAttribute('aria-pressed', 'false')

    await page.screenshot({ path: `${SCREENSHOT_DIR}/08-theme-selection-state.png`, fullPage: true })

    // Close settings
    await page.keyboard.press('Escape')
  })
})
