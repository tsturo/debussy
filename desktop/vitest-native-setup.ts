/**
 * Vitest global setup — resolves the better-sqlite3 ABI mismatch.
 *
 * The postinstall hook (electron-rebuild) compiles better-sqlite3 for
 * Electron's embedded Node (NODE_MODULE_VERSION 140). Vitest runs under the
 * system Node (NMV 141), so the Electron binary fails to load.
 *
 * Strategy: before any test worker starts, swap the binary for a
 * system-Node-compatible prebuilt; after all tests finish, restore the
 * Electron binary so `npm run dev` keeps working.
 *
 * The system-Node binary is cached alongside the Electron binary so that
 * subsequent test runs skip the network download.
 */

import { copyFileSync, existsSync } from 'fs'
import { execFileSync } from 'child_process'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const DESKTOP = dirname(fileURLToPath(import.meta.url))
const BS3_DIR = join(DESKTOP, 'node_modules/better-sqlite3')
const RELEASE = join(BS3_DIR, 'build/Release')
const BINARY = join(RELEASE, 'better_sqlite3.node')
const ELECTRON_BACKUP = join(RELEASE, 'better_sqlite3.electron.node')
const NODE_CACHE = join(RELEASE, 'better_sqlite3.node_napi.node')

/**
 * Returns true when the current binary cannot be loaded by the system Node.
 * Spawns a child `node` process to probe the binary; ERR_DLOPEN_FAILED (exit
 * code 1) means it was compiled for a different ABI (e.g., Electron's Node).
 */
function binaryNeedsSwap(): boolean {
  if (!existsSync(BINARY)) return true
  try {
    execFileSync(process.execPath, ['-e', `require(${JSON.stringify(BINARY)})`], {
      stdio: 'pipe',
    })
    return false
  } catch {
    return true
  }
}

export async function setup(): Promise<void> {
  if (!binaryNeedsSwap()) return

  // Save the Electron-compiled binary so teardown can restore it.
  if (existsSync(BINARY)) {
    copyFileSync(BINARY, ELECTRON_BACKUP)
  }

  if (existsSync(NODE_CACHE)) {
    // Fast path: reuse the previously downloaded system-Node binary.
    copyFileSync(NODE_CACHE, BINARY)
  } else {
    // Download a prebuilt for the current system Node (or build from source).
    // better-sqlite3's install script runs: prebuild-install || node-gyp rebuild
    execFileSync('npm', ['run', 'install'], { cwd: BS3_DIR, stdio: 'pipe' })
    // Cache for future runs so subsequent test invocations skip the download.
    if (existsSync(BINARY)) {
      copyFileSync(BINARY, NODE_CACHE)
    }
  }
}

export async function teardown(): Promise<void> {
  // Restore the Electron binary so `npm run dev` continues to work.
  if (existsSync(ELECTRON_BACKUP)) {
    copyFileSync(ELECTRON_BACKUP, BINARY)
  }
}
