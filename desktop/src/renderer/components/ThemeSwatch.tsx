import type { Theme } from '../store/app-store'

export function ThemeSwatch({ theme }: { theme: Theme }) {
  if (theme === 'dark') {
    return (
      <div
        aria-hidden="true"
        style={{
          width: '100%',
          height: 52,
          borderRadius: 6,
          background: '#0a0f1a',
          border: '1px solid rgba(232,237,243,0.08)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ height: 6, width: '60%', borderRadius: 3, background: '#131829' }} />
        <div style={{ height: 4, width: '80%', borderRadius: 3, background: 'rgba(108,92,231,0.4)' }} />
        <div style={{ height: 4, width: '45%', borderRadius: 3, background: 'rgba(232,237,243,0.12)' }} />
      </div>
    )
  }

  if (theme === 'light') {
    return (
      <div
        aria-hidden="true"
        style={{
          width: '100%',
          height: 52,
          borderRadius: 6,
          background: '#ffffff',
          border: '1px solid #d0d0e0',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ height: 6, width: '60%', borderRadius: 3, background: '#e8e8f0' }} />
        <div style={{ height: 4, width: '80%', borderRadius: 3, background: 'rgba(108,92,231,0.35)' }} />
        <div style={{ height: 4, width: '45%', borderRadius: 3, background: '#d0d0e0' }} />
      </div>
    )
  }

  // System: split half-half
  return (
    <div
      aria-hidden="true"
      style={{
        width: '100%',
        height: 52,
        borderRadius: 6,
        border: '1px solid var(--t-border)',
        overflow: 'hidden',
        display: 'flex',
      }}
    >
      <div
        style={{
          flex: 1,
          background: '#ffffff',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ height: 6, width: '100%', borderRadius: 3, background: '#f7f7fb' }} />
        <div style={{ height: 4, width: '100%', borderRadius: 3, background: 'rgba(108,92,231,0.3)' }} />
      </div>
      <div
        style={{
          flex: 1,
          background: '#0a0f1a',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          padding: 6,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ height: 6, width: '100%', borderRadius: 3, background: '#131829' }} />
        <div style={{ height: 4, width: '100%', borderRadius: 3, background: 'rgba(108,92,231,0.4)' }} />
      </div>
    </div>
  )
}
