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

  await app.close()
})

test('default launch applies dark theme', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  // Clear any saved preference so we test the true default behaviour, then reload
  await page.evaluate(() => localStorage.removeItem('debussy-theme'))
  await page.reload()
  await page.waitForLoadState('domcontentloaded')

  // data-theme must be 'dark' on fresh launch with no saved preference
  const theme = await page.evaluate(() =>
    document.documentElement.getAttribute('data-theme'),
  )
  expect(theme).toBe('dark')

  // Background color must match the dark theme spec (#0a0f1a)
  const bgColor = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--t-bg').trim(),
  )
  expect(bgColor).toBe('#0a0f1a')

  await page.screenshot({ path: `${SCREENSHOT_DIR}/09-dark-launch.png`, fullPage: true })

  await app.close()
})

test('localStorage theme=light launches in light theme', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  // Set localStorage to 'light' and reload — simulates a user who previously chose light
  await page.evaluate(() => localStorage.setItem('debussy-theme', 'light'))
  await page.reload()
  await page.waitForLoadState('domcontentloaded')

  const theme = await page.evaluate(() =>
    document.documentElement.getAttribute('data-theme'),
  )
  expect(theme).toBe('light')

  await app.close()
})

test('localStorage theme=system follows OS preference', async () => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })

  const app = await electron.launch({ args: [APP_MAIN] })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')

  // Set localStorage to 'system' and reload
  await page.evaluate(() => localStorage.setItem('debussy-theme', 'system'))
  await page.reload()
  await page.waitForLoadState('domcontentloaded')

  // Should resolve to either dark or light based on OS preference — never null
  const theme = await page.evaluate(() =>
    document.documentElement.getAttribute('data-theme'),
  )
  expect(['dark', 'light']).toContain(theme)

  await app.close()
})
