import React, { useState } from 'react'
import type { AgentRole, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { formatElapsed } from '../lib/format'

export interface AgentBarAgent {
  taskId: string
  name: string
  role: AgentRole
  stage: Stage
  startedAt: number
}

export interface AgentBarProps {
  agents: AgentBarAgent[]
  watcherRunning: boolean
  onAgentClick: (taskId: string) => void
  onWatcherToggle: () => Promise<void>
}

const MAX_VISIBLE = 8

function AgentAvatar({
  agent,
  onClick,
}: {
  agent: AgentBarAgent
  onClick: () => void
}) {
  const [hovered, setHovered] = useState(false)
  const stageColor = STAGE_COLORS[agent.stage]?.color ?? '#6b7388'
  const initial = agent.name.charAt(0).toUpperCase()
  const elapsed = formatElapsed(agent.startedAt)

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          border: `2px solid ${stageColor}`,
          background: hexToRgba(stageColor, 0.12),
          boxShadow: `0 0 0 2px ${hexToRgba(stageColor, 0.20)}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 700,
          fontSize: 12,
          color: stageColor,
          cursor: 'pointer',
          padding: 0,
          animation: 'agent-pulse 2s ease-in-out infinite',
          flexShrink: 0,
          '--pulse-color': hexToRgba(stageColor, 0.20),
        } as React.CSSProperties}
        aria-label={`${agent.name} · ${agent.role} · ${agent.taskId} · ${elapsed}`}
      >
        {initial}
      </button>

      {hovered && (
        <div
          style={{
            position: 'absolute',
            top: 38,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderRadius: 'var(--t-radius-sm)',
            padding: '4px 8px',
            whiteSpace: 'nowrap',
            fontSize: 11,
            color: 'var(--t-text-2)',
            pointerEvents: 'none',
            zIndex: 100,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}
        >
          {agent.name} · {agent.role} · {agent.taskId} · {elapsed}
        </div>
      )}
    </div>
  )
}

export function AgentBar({ agents, watcherRunning, onAgentClick, onWatcherToggle }: AgentBarProps) {
  const visible = agents.slice(0, MAX_VISIBLE)
  const overflow = agents.length - MAX_VISIBLE

  return (
    <>
      <style>{`
        @keyframes agent-pulse {
          0%, 100% { box-shadow: 0 0 0 2px var(--pulse-color, rgba(108,92,231,0.20)); opacity: 1; }
          50%       { box-shadow: 0 0 0 2px var(--pulse-color, rgba(108,92,231,0.20)); opacity: 0.4; }
        }
      `}</style>

      <div
        style={{
          height: 48,
          background: 'var(--t-surface)',
          borderBottom: '1px solid var(--t-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          flexShrink: 0,
        }}
        role="toolbar"
        aria-label="Active agents"
      >
        {/* Left: agent avatars */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {visible.map((agent) => (
            <AgentAvatar
              key={agent.taskId}
              agent={agent}
              onClick={() => onAgentClick(agent.taskId)}
            />
          ))}

          {overflow > 0 && (
            <div
              style={{
                height: 24,
                padding: '0 10px',
                borderRadius: 'var(--t-radius-pill)',
                background: 'var(--t-surface)',
                display: 'flex',
                alignItems: 'center',
                fontSize: 11,
                fontWeight: 500,
                color: 'var(--t-text-3)',
                flexShrink: 0,
              }}
            >
              +{overflow}
            </div>
          )}
        </div>

        {/* Right: watcher status (clickable toggle) */}
        <button
          onClick={() => {
            const confirmed = watcherRunning
              ? window.confirm('Stop watcher? This will kill all running agents.')
              : window.confirm('Start watcher?')
            if (confirmed) onWatcherToggle()
          }}
          title={watcherRunning ? 'Click to stop watcher' : 'Click to start watcher'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: 'var(--t-radius-sm)',
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: watcherRunning ? 'var(--t-teal)' : 'var(--t-text-3)',
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: 11,
              color: watcherRunning ? 'var(--t-teal)' : 'var(--t-text-3)',
            }}
          >
            {watcherRunning ? 'watching' : 'stopped'}
          </span>
        </button>
      </div>
    </>
  )
}

/** Convert a hex color string to rgba() with the given alpha. */
function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '')
  const r = parseInt(clean.substring(0, 2), 16)
  const g = parseInt(clean.substring(2, 4), 16)
  const b = parseInt(clean.substring(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
