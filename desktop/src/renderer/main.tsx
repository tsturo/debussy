import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './globals.css'
import App from './App'

// Apply theme immediately — before first render — to avoid flash of wrong theme.
// Priority: localStorage value → 'dark' default (no system guessing on cold start).
;(function applyInitialTheme() {
  let pref: string | null = null
  try {
    pref = localStorage.getItem('debussy-theme')
  } catch {
    // localStorage may be unavailable in some contexts
  }

  let resolved: 'dark' | 'light'
  if (pref === 'light') {
    resolved = 'light'
  } else if (pref === 'system') {
    resolved = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } else {
    // No saved preference (or explicit 'dark') → default dark per design spec
    resolved = 'dark'
  }

  document.documentElement.setAttribute('data-theme', resolved)
})()

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
)
