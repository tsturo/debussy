#!/usr/bin/env node
/**
 * Generate Debussy app icon from SVG source.
 *
 * Converts desktop/build/icon.svg to platform-specific formats:
 *   - desktop/build/icon.png  (1024x1024, used for Linux and as source)
 *   - desktop/build/icon.icns (macOS, generated via iconutil)
 *
 * Requirements (macOS): sips, iconutil (both ship with macOS)
 */

import { execFileSync } from 'child_process'
import { existsSync, mkdirSync, rmSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const buildDir = resolve(__dirname, '../build')
const svgPath = resolve(buildDir, 'icon.svg')
const pngPath = resolve(buildDir, 'icon.png')

function sips(args, desc) {
  console.log(`→ ${desc}`)
  try {
    execFileSync('sips', args, { stdio: 'pipe' })
  } catch (err) {
    console.error(`  Failed: ${err.stderr?.toString() || err.message}`)
    throw err
  }
}

// 1. Convert SVG → PNG (1024×1024) using sips (macOS built-in)
if (!existsSync(svgPath)) {
  console.error(`SVG source not found: ${svgPath}`)
  process.exit(1)
}

sips(['-s', 'format', 'png', svgPath, '--out', pngPath, '-z', '1024', '1024'], 'SVG → PNG (1024×1024)')

// 2. macOS: build .icns via iconutil
if (process.platform === 'darwin') {
  const iconsetDir = resolve(buildDir, 'icon.iconset')
  mkdirSync(iconsetDir, { recursive: true })

  const sizes = [16, 32, 64, 128, 256, 512, 1024]
  for (const size of sizes) {
    const out = resolve(iconsetDir, `icon_${size}x${size}.png`)
    sips(['-z', String(size), String(size), pngPath, '--out', out], `Resize → ${size}x${size}`)

    // Retina variants (2x) up to 512@2x = 1024
    if (size <= 512) {
      const out2x = resolve(iconsetDir, `icon_${size}x${size}@2x.png`)
      const size2x = size * 2
      sips(['-z', String(size2x), String(size2x), pngPath, '--out', out2x], `Resize → ${size}x${size}@2x`)
    }
  }

  const icnsPath = resolve(buildDir, 'icon.icns')
  execFileSync('iconutil', ['-c', 'icns', iconsetDir, '-o', icnsPath], { stdio: 'pipe' })
  console.log('→ iconset → .icns')
  rmSync(iconsetDir, { recursive: true })
  console.log(`✓ macOS icon: ${icnsPath}`)
}

console.log(`✓ Icon generation complete. Output: ${buildDir}/`)
