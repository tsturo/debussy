import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ConductorMessage, LogEntry, Stage } from '../shared/types'

import { Sidebar } from './components/Sidebar'
import { Board } from './components/Board'
import { Conductor } from './components/Conductor'
import { TaskDetailShell } from './components/TaskDetailShell'
import { TaskDetailBody } from './components/TaskDetailBody'
import { Settings } from './components/Settings'
import { CommandPalette } from './components/CommandPalette'
import type { PaletteAction } from './components/CommandPalette'

import { useAppStore } from './store/app-store'
import { useBreakpoint } from './lib/use-media-query'

// ── App ──────────────────────────────────────────────────────────────────────

function App() {
  // ── Store selectors ────────────────────────────────────────────────────────
  const tasks = useAppStore((s) => s.tasks)
  const agents = useAppStore((s) => s.agents)
  const config = useAppStore((s) => s.config)
  const watcherRunning = useAppStore((s) => s.watcherRunning)
  const selectedTaskId = useAppStore((s) => s.selectedTaskId)
  const conductorMessages = useAppStore((s) => s.conductorMessages)

  const fetchAll = useAppStore((s) => s.fetchAll)
  const selectTask = useAppStore((s) => s.selectTask)
  const advanceTask = useAppStore((s) => s.advanceTask)
  const blockTask = useAppStore((s) => s.blockTask)
  const commentOnTask = useAppStore((s) => s.commentOnTask)
  const addConductorMessage = useAppStore((s) => s.addConductorMessage)
  const theme = useAppStore((s) => s.theme)
  const setTheme = useAppStore((s) => s.setTheme)

  // ── Theme application ──────────────────────────────────────────────────────

  useEffect(() => {
    function resolveTheme(pref: typeof theme): 'dark' | 'light' {
      if (pref !== 'system') return pref
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }

    function applyTheme() {
      document.documentElement.setAttribute('data-theme', resolveTheme(theme))
    }

    applyTheme()

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', applyTheme)
      return () => mq.removeEventListener('change', applyTheme)
    }
  }, [theme])

  // ── Responsive breakpoints ─────────────────────────────────────────────────
  const { isLarge, isMedium, isSmall } = useBreakpoint()

  // Manual overrides — null means "use breakpoint default"
  const [sidebarOverride, setSidebarOverride] = useState<boolean | null>(null)
  const [conductorOverride, setConductorOverride] = useState<boolean | null>(null)

  // Reset overrides when the breakpoint boundary changes so the layout snaps
  // back to the breakpoint default on resize.
  const prevBreakpoint = useRef({ isLarge, isMedium })
  useEffect(() => {
    const prev = prevBreakpoint.current
    if (prev.isLarge !== isLarge || prev.isMedium !== isMedium) {
      setSidebarOverride(null)
      setConductorOverride(null)
      prevBreakpoint.current = { isLarge, isMedium }
    }
  }, [isLarge, isMedium])

  // Breakpoint defaults:
  //   Large  (≥1920px): sidebar expanded, conductor visible, backlog shown
  //   Medium (1366–1920px): sidebar collapsed, conductor hidden, no backlog
  //   Small  (<1366px):  sidebar collapsed, conductor hidden (overlay on toggle)
  const defaultSidebarCollapsed = !isLarge
  const defaultConductorVisible = isLarge

  // Effective UI state — user override wins; breakpoint default is the fallback
  const sidebarCollapsed = sidebarOverride ?? defaultSidebarCollapsed
  const conductorVisible = conductorOverride ?? defaultConductorVisible

  const handleToggleSidebar = useCallback(() => {
    setSidebarOverride((prev) => !(prev ?? defaultSidebarCollapsed))
  }, [defaultSidebarCollapsed])

  const handleToggleConductor = useCallback(() => {
    setConductorOverride((prev) => !(prev ?? defaultConductorVisible))
  }, [defaultConductorVisible])

  // ── Settings modal state ──────────────────────────────────────────────────
  const [settingsOpen, setSettingsOpen] = useState(false)

  // ── Command palette state ──────────────────────────────────────────────────
  const [paletteOpen, setPaletteOpen] = useState(false)

  // ── Task log entries (fetched when selectedTaskId changes) ────────────────
  const [taskLogEntries, setTaskLogEntries] = useState<LogEntry[]>([])

  useEffect(() => {
    if (!selectedTaskId) {
      setTaskLogEntries([])
      return
    }
    window.debussy.tasks.get(selectedTaskId).then((result) => {
      setTaskLogEntries(result?.log ?? [])
    }).catch(() => {
      setTaskLogEntries([])
    })
  }, [selectedTaskId])

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

      // Escape → close palette first, then task detail
      if (e.key === 'Escape') {
        if (paletteOpen) {
          setPaletteOpen(false)
          return
        }
        selectTask(null)
        return
      }

      // Cmd/Ctrl+, → open Settings
      if (meta && e.key === ',') {
        e.preventDefault()
        setSettingsOpen(true)
        return
      }

      // Cmd/Ctrl+\ → toggle Conductor panel
      if (meta && e.key === '\\') {
        e.preventDefault()
        handleToggleConductor()
        return
      }

      // Cmd/Ctrl+K → open command palette
      if (meta && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [selectTask, handleToggleConductor, paletteOpen])

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

  // ── Command palette actions ────────────────────────────────────────────────

  const paletteActions: PaletteAction[] = useMemo(() => [
    // Tasks
    {
      id: 'new-task',
      name: 'New Task',
      category: 'Tasks',
      shortcut: null,
      action: () => { console.log('new task') },
    },
    {
      id: 'advance-task',
      name: 'Advance Task...',
      category: 'Tasks',
      action: () => {
        const id = window.prompt('Task ID to advance:')
        if (id?.trim()) advanceTask(id.trim())
      },
    },
    // Navigation
    {
      id: 'toggle-conductor',
      name: 'Toggle Conductor Panel',
      category: 'Navigation',
      shortcut: '⌘\\',
      action: handleToggleConductor,
    },
    {
      id: 'toggle-sidebar',
      name: 'Toggle Sidebar',
      category: 'Navigation',
      action: handleToggleSidebar,
    },
    {
      id: 'open-settings',
      name: 'Open Settings',
      category: 'Navigation',
      shortcut: '⌘,',
      action: () => setSettingsOpen(true),
    },
    // Appearance
    {
      id: 'theme-dark',
      name: 'Switch to Dark Theme',
      category: 'Appearance',
      action: () => setTheme('dark'),
    },
    {
      id: 'theme-light',
      name: 'Switch to Light Theme',
      category: 'Appearance',
      action: () => setTheme('light'),
    },
    {
      id: 'theme-system',
      name: 'Use System Theme',
      category: 'Appearance',
      action: () => setTheme('system'),
    },
  ], [advanceTask, handleToggleConductor, handleToggleSidebar, setTheme])

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
        onSettingsClick={() => setSettingsOpen(true)}
        onAddProject={() => console.log('add project clicked')}
      />

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div
        className="main-area"
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}
      >
        {/* Toggle sidebar button (thin strip on left edge of main area) */}
        <button
          onClick={handleToggleSidebar}
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
            showBacklog={isLarge}
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
              logEntries={taskLogEntries}
              onComment={(message) =>
                selectedTaskId && commentOnTask(selectedTaskId, message)
              }
            />
          )}
        </TaskDetailShell>
      </div>

      {/* ── Conductor panel ────────────────────────────────────────────────── */}
      {/* On small screens (< 1366px) the conductor floats as an overlay so it
          doesn't shrink the board. On medium/large it sits inline as a flex
          sibling. */}
      {isSmall ? (
        conductorVisible && (
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              zIndex: 100,
              display: 'flex',
            }}
          >
            <Conductor
              messages={conductorMessages}
              isVisible={conductorVisible}
              onSend={handleSendConductorMessage}
            />
          </div>
        )
      ) : (
        <Conductor
          messages={conductorMessages}
          isVisible={conductorVisible}
          onSend={handleSendConductorMessage}
        />
      )}

      {/* ── Settings modal ──────────────────────────────────────────────────── */}
      <Settings
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

      {/* ── Command palette ─────────────────────────────────────────────────── */}
      <CommandPalette
        isOpen={paletteOpen}
        actions={paletteActions}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}

export default App
