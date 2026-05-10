import { useEffect, useState } from 'react'
import type { ConductorMessage } from '../shared/types'

import { Sidebar } from './components/Sidebar'
import { Board } from './components/Board'
import { Conductor } from './components/Conductor'
import { TaskDetailShell } from './components/TaskDetailShell'
import { TaskDetailBody } from './components/TaskDetailBody'

import {
  MOCK_TASKS,
  MOCK_AGENTS,
  MOCK_CONDUCTOR_MESSAGES,
  MOCK_LOG_ENTRIES_BY_TASK,
  MOCK_CONFIG,
} from './lib/mock-data'

// ── Mock projects for the sidebar ───────────────────────────────────────────

const MOCK_PROJECTS = [
  { name: 'auth-system', isActive: true, agentCount: 4, status: 'active' as const },
  { name: 'api-gateway', isActive: false, agentCount: 1, status: 'running' as const },
  { name: 'frontend-v2', isActive: false, agentCount: 0, status: 'idle' as const },
]

// ── App ──────────────────────────────────────────────────────────────────────

function App() {
  // ── Core UI state ──────────────────────────────────────────────────────────
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [conductorVisible, setConductorVisible] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // ── Conductor messages (mock echo on send) ─────────────────────────────────
  const [conductorMessages, setConductorMessages] = useState<ConductorMessage[]>(
    MOCK_CONDUCTOR_MESSAGES,
  )

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey

      // Escape → close TaskDetail
      if (e.key === 'Escape') {
        setSelectedTaskId(null)
        return
      }

      // Cmd/Ctrl+\ → toggle Conductor panel
      if (meta && e.key === '\\') {
        e.preventDefault()
        setConductorVisible((v) => !v)
        return
      }

      // Cmd/Ctrl+K → placeholder (command palette — future)
      if (meta && e.key === 'k') {
        e.preventDefault()
        console.log('command palette — not yet implemented')
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // ── Derived state ──────────────────────────────────────────────────────────

  const selectedTask = selectedTaskId
    ? MOCK_TASKS.find((t) => t.id === selectedTaskId) ?? null
    : null

  const selectedAgent = selectedTaskId
    ? MOCK_AGENTS.find((a) => a.taskId === selectedTaskId) ?? null
    : null

  const selectedLogEntries = selectedTaskId
    ? (MOCK_LOG_ENTRIES_BY_TASK[selectedTaskId] ?? [])
    : []

  const lastEvent = (() => {
    // Find the most recent transition across all log entries
    let latest: { timestamp: string; message: string } | null = null
    for (const entries of Object.values(MOCK_LOG_ENTRIES_BY_TASK)) {
      for (const e of entries) {
        if (e.type === 'transition') {
          if (!latest || e.timestamp > latest.timestamp) {
            latest = e
          }
        }
      }
    }
    if (!latest) return ''
    // Shorten: extract task id and strip the verbose prefix
    return latest.message.replace('advanced ', '').replace('released — ', '')
  })()

  // ── Interaction handlers ───────────────────────────────────────────────────

  function handleSendConductorMessage(message: string) {
    const userMsg: ConductorMessage = {
      id: `cm-user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    const echoMsg: ConductorMessage = {
      id: `cm-echo-${Date.now()}`,
      role: 'assistant',
      content: `(mock echo) You said: "${message}"`,
      timestamp: Date.now() + 500,
    }
    setConductorMessages((prev) => [...prev, userMsg, echoMsg])
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="app-shell"
      style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}
    >
      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <Sidebar
        workspaceName="debussy"
        workspaceInitial="D"
        projects={MOCK_PROJECTS}
        collapsed={sidebarCollapsed}
        onProjectSelect={(name) => console.log('project selected:', name)}
        onSettingsClick={() => console.log('settings clicked')}
        onAddProject={() => console.log('add project clicked')}
      />

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div
        className="main-area"
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}
      >
        {/* Toggle sidebar button (thin strip on left edge of main area) */}
        <button
          onClick={() => setSidebarCollapsed((v) => !v)}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            position: 'absolute',
            left: sidebarCollapsed ? 48 : 248,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            width: 16,
            height: 32,
            background: 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderLeft: 'none',
            borderRadius: '0 6px 6px 0',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--t-text-3)',
            padding: 0,
            transition: 'left var(--t-dur-base) var(--t-ease)',
          }}
        >
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none" aria-hidden="true">
            <path
              d={sidebarCollapsed ? 'M2 1l4 3-4 3' : 'M6 1L2 4l4 3'}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {/* Board fills all available vertical space above the detail panel */}
        <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
          <Board
            tasks={MOCK_TASKS}
            agents={MOCK_AGENTS}
            config={MOCK_CONFIG}
            selectedTaskId={selectedTaskId}
            watcherRunning={true}
            onTaskSelect={(taskId) => setSelectedTaskId(taskId)}
            onNewTask={() => console.log('new task clicked')}
          />
        </div>

        {/* TaskDetail panel (collapsed strip when no task selected) */}
        <TaskDetailShell
          task={selectedTask}
          agent={
            selectedAgent
              ? { name: selectedAgent.name, stage: selectedAgent.stage }
              : null
          }
          watcherRunning={true}
          agentCount={MOCK_AGENTS.length}
          lastEvent={lastEvent}
          onClose={() => setSelectedTaskId(null)}
          onAdvance={() => console.log('advance', selectedTaskId)}
          onBlock={() => console.log('block', selectedTaskId)}
        >
          {selectedTask && (
            <TaskDetailBody
              task={selectedTask}
              logEntries={selectedLogEntries}
              onComment={(message) => console.log('comment', selectedTaskId, message)}
            />
          )}
        </TaskDetailShell>
      </div>

      {/* ── Conductor panel (conditionally shown) ──────────────────────────── */}
      {conductorVisible && (
        <Conductor
          messages={conductorMessages}
          isVisible={conductorVisible}
          onSend={handleSendConductorMessage}
        />
      )}
    </div>
  )
}

export default App
