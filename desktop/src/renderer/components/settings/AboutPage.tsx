import { useEffect, useState } from 'react'

interface AppInfo {
  appVersion: string
  electronVersion: string
  nodeVersion: string
  chromeVersion: string
}

// ── Info row ──────────────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '7px 0',
        borderBottom: '1px solid var(--t-border)',
      }}
    >
      <span style={{ fontSize: 12, color: 'var(--t-text-3)' }}>{label}</span>
      <span
        style={{
          fontSize: 12,
          color: 'var(--t-text-2)',
          fontFamily: 'var(--t-font-mono, monospace)',
        }}
      >
        {value}
      </span>
    </div>
  )
}

// ── About page ────────────────────────────────────────────────────────────────

export function AboutPage() {
  const [info, setInfo] = useState<AppInfo | null>(null)

  useEffect(() => {
    window.debussy.app.info().then(setInfo).catch(() => {
      // Fallback: show dashes if IPC fails (e.g., in browser preview)
      setInfo({
        appVersion:      '—',
        electronVersion: '—',
        nodeVersion:     '—',
        chromeVersion:   '—',
      })
    })
  }, [])

  function handleGitHubClick(e: React.MouseEvent<HTMLAnchorElement>) {
    e.preventDefault()
    window.debussy.shell.openExternal('https://github.com/tsturo/debussy')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* ── App identity ── */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* App name with Tonale gradient */}
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            background: 'linear-gradient(135deg, var(--t-purple) 0%, var(--t-blue, #5b9cf6) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            lineHeight: 1.2,
          }}
        >
          Debussy Desktop
        </div>
        <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>
          Pipeline orchestration for AI coding agents
        </div>
      </section>

      {/* ── Version badge ── */}
      {info && (
        <section>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 10px',
              borderRadius: 'var(--t-radius-sm)',
              background: 'color-mix(in srgb, var(--t-purple) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--t-purple) 25%, transparent)',
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--t-purple)',
                fontFamily: 'var(--t-font-mono, monospace)',
              }}
            >
              v{info.appVersion}
            </span>
          </div>
        </section>
      )}

      {/* ── System info ── */}
      <section>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--t-text-3)',
            marginBottom: 8,
          }}
        >
          System
        </div>
        <div style={{ borderTop: '1px solid var(--t-border)' }}>
          {info ? (
            <>
              <InfoRow label="Electron" value={info.electronVersion} />
              <InfoRow label="Node"     value={info.nodeVersion} />
              <InfoRow label="Chrome"   value={info.chromeVersion} />
            </>
          ) : (
            <div style={{ padding: '12px 0', fontSize: 12, color: 'var(--t-text-3)' }}>
              Loading…
            </div>
          )}
        </div>
      </section>

      {/* ── Links ── */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--t-text-3)',
            marginBottom: 2,
          }}
        >
          Links
        </div>
        <a
          href="https://github.com/tsturo/debussy"
          onClick={handleGitHubClick}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'var(--t-purple)',
            textDecoration: 'none',
            width: 'fit-content',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.textDecoration = 'underline'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.textDecoration = 'none'
          }}
        >
          {/* GitHub icon */}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
          </svg>
          GitHub Repository
        </a>
      </section>

      {/* ── Design system footer ── */}
      <div
        style={{
          marginTop: 'auto',
          paddingTop: 16,
          borderTop: '1px solid var(--t-border)',
          fontSize: 12,
          color: 'var(--t-text-3)',
        }}
      >
        Tonale Design System v0.1.0
      </div>
    </div>
  )
}

export default AboutPage
