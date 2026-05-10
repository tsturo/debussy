import { useEffect, useMemo } from 'react'
import type { ConductorMessage, Stage } from '../shared/types'

import { Sidebar } from './components/Sidebar'
import { Board } from './components/Board'
import { Conductor } from './components/Conductor'
import { TaskDetailShell } from './components/TaskDetailShell'
import { TaskDetailBody } from './components/TaskDetailBody'

import { useAppStore } from './store/app-store'

// ── App ──────────────────────────────────────────────────────────────────────

function App() {
  // ── Store selectors ────────────────────────────────────────────────────────
  const tasks = useAppStore((s) => s.tasks)
  const agents = useAppStore((s) => s.agents)
  const config = useAppStore((s) => s.config)
  const watcherRunning = useAppStore((s) => s.watcherRunning)
  const selectedTaskId = useAppStore((s) => s.selectedTaskId)
  const conductorVisible = useAppStore((s) => s.conductorVisible)
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const conductorMessages = useAppStore((s) => s.conductorMessages)

  const fetchAll = useAppStore((s) => s.fetchAll)
  const selectTask = useAppStore((s) => s.selectTask)
  const toggleConductor = useAppStore((s) => s.toggleConductor)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const advanceTask = useAppStore((s) => s.advanceTask)
  const blockTask = useAppStore((s) => s.blockTask)
  const commentOnTask = useAppStore((s) => s.commentOnTask)
  const addConductorMessage = useAppStore((s) => s.addConductorMessage)

  // ── Polling ────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 5000)
    return () => clearInterval(interval)
  }, [fetchAll])

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey

      // Escape → close TaskDetail
      if (e.key === 'Escape') {
        selectTask(null)
        return
      }

      // Cmd/Ctrl+\ → toggle Conductor panel
      if (meta && e.key === '\\') {
        e.preventDefault()
        toggleConductor()
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
  }, [selectTask, toggleConductor])

  // ── Derived state ──────────────────────────────────────────────────────────

  const agentCount = Object.keys(agents).length

  const selectedTask = selectedTaskId
    ? tasks.find((t) => t.id === selectedTaskId) ?? null
    : null

  const selectedAgent = selectedTaskId ? (agents[selectedTaskId] ?? null) : null

  // Transform WatcherState (Record<taskId, AgentInfo>) → flat array for Board.
  // Use the task's stage so the column placement matches the kanban board.
  const agentList = useMemo(() => {
    const taskStageMap = new Map(tasks.map((t) => [t.id, t.stage]))
    return Object.entries(agents).map(([taskId, info]) => ({
      taskId,
      name: info.agent,
      role: info.role,
      stage: (taskStageMap.get(taskId) ?? 'development') as Stage,
      startedAt: info.started_at * 1000,  // convert Unix seconds → ms
    }))
  }, [agents, tasks])

  const lastEvent = (() => {
    if (agentList.length === 0) return ''
    const sorted = [...agentList].sort((a, b) => b.startedAt - a.startedAt)
    const latest = sorted[0]
    return `${latest.name} working on ${latest.taskId}`
  })()

  // ── Conductor send handler ─────────────────────────────────────────────────

  function handleSendConductorMessage(message: string) {
    const userMsg: ConductorMessage = {
      id: `cm-user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    addConductorMessage(userMsg)
    // Echo for dev/test feedback — real conductor integration comes later
    const echoMsg: ConductorMessage = {
      id: `cm-echo-${Date.now()}`,
      role: 'assistant',
      content: `(echo) You said: "${message}"`,
      timestamp: Date.now() + 500,
    }
    addConductorMessage(echoMsg)
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
        projects={[]}
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
          onClick={toggleSidebar}
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
            tasks={tasks}
            agents={agentList}
            config={config}
            selectedTaskId={selectedTaskId}
            watcherRunning={watcherRunning}
            onTaskSelect={(taskId) => selectTask(taskId)}
            onNewTask={() => console.log('new task clicked')}
          />
        </div>

        {/* TaskDetail panel (collapsed strip when no task selected) */}
        <TaskDetailShell
          task={selectedTask}
          agent={
            selectedAgent && selectedTask
              ? { name: selectedAgent.agent, stage: selectedTask.stage }
              : null
          }
          watcherRunning={watcherRunning}
          agentCount={agentCount}
          lastEvent={lastEvent}
          onClose={() => selectTask(null)}
          onAdvance={() => selectedTaskId && advanceTask(selectedTaskId)}
          onBlock={() => selectedTaskId && blockTask(selectedTaskId)}
        >
          {selectedTask && (
            <TaskDetailBody
              task={selectedTask}
              logEntries={[]}
              onComment={(message) =>
                selectedTaskId && commentOnTask(selectedTaskId, message)
              }
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
