import { test, expect, _electron as electron } from '@playwright/test'
import { resolve } from 'path'
import { mkdirSync } from 'fs'

const APP_MAIN = resolve(__dirname, '..', '..', 'out', 'main', 'index.js')
const SCREENSHOT_DIR = resolve(__dirname, '..', '..', 'screenshots')

test('app launches and shows board', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  // Verify app renders
  await expect(page.locator('body')).toBeVisible()
  await page.screenshot({ path: `${SCREENSHOT_DIR}/01-launch.png`, fullPage: true })

  // Verify main UI zones exist
  // (use flexible selectors — inspect actual rendered markup)
  await expect(page.locator('.app-shell')).toBeVisible()
  await expect(page.locator('header')).toBeVisible()

  await app.close()
})
