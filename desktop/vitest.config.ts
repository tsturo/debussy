/**
 * Vitest configuration for debussy-desktop.
 *
 * NATIVE MODULE ABI MISMATCH (better-sqlite3)
 * -------------------------------------------
 * The postinstall hook runs electron-rebuild, which compiles better-sqlite3
 * for Electron's embedded Node (NODE_MODULE_VERSION 140). Vitest runs under
 * the system Node (currently NMV 141), so the Electron binary cannot load and
 * all db-reader tests skip/fail with ERR_DLOPEN_FAILED.
 *
 * Fix (Option A — dual build via globalSetup):
 *   vitest-native-setup.ts detects the ABI mismatch before any test worker
 *   starts, downloads a prebuilt system-Node binary (or builds from source),
 *   and caches it at better_sqlite3.node_napi.node so subsequent test runs
 *   use a fast file-copy instead of a network download.  After all tests
 *   finish, teardown() restores the Electron binary so `npm run dev` works.
 */
import { defineConfig } from 'vitest/config'
import { resolve } from 'path'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/__tests__/**/*.test.ts'],
    globalSetup: ['./vitest-native-setup.ts'],
  },
  resolve: {
    alias: {
      '@shared': resolve(__dirname, 'src/shared'),
    },
  },
})
