import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ConductorMessage, LogEntry, Stage, Task } from '../shared/types'
import { useWorkspaceHandlers } from './hooks/useWorkspaceHandlers'

import { Sidebar } from './components/Sidebar'
import { Board } from './components/Board'
import { Conductor } from './components/Conductor'
import { TaskDetailShell } from './components/TaskDetailShell'
import { TaskDetailBody } from './components/TaskDetailBody'
import { Settings } from './components/Settings'
import { NewTaskDialog } from './components/NewTaskDialog'
import { CommandPalette } from './components/CommandPalette'
import type { PaletteAction } from './components/CommandPalette'

import { useAppStore } from './store/app-store'
import { useBreakpoint } from './lib/use-media-query'

function App() {
  // ── Store selectors ────────────────────────────────────────────────────────
  const tasks = useAppStore((s) => s.tasks)
  const agents = useAppStore((s) => s.agents)
  const config = useAppStore((s) => s.config)
  const watcherRunning = useAppStore((s) => s.watcherRunning)
  const selectedTaskId = useAppStore((s) => s.selectedTaskId)
  const conductorMessages = useAppStore((s) => s.conductorMessages)

  const workspaceGroups = useAppStore((s) => s.workspaceGroups)
  const activeGroupId = useAppStore((s) => s.activeGroupId)
  const activeProjectPath = useAppStore((s) => s.activeProjectPath)

  const fetchAll = useAppStore((s) => s.fetchAll)
  const fetchWorkspaces = useAppStore((s) => s.fetchWorkspaces)
  const selectTask = useAppStore((s) => s.selectTask)
  const advanceTask = useAppStore((s) => s.advanceTask)
  const moveTask = useAppStore((s) => s.moveTask)
  const blockTask = useAppStore((s) => s.blockTask)
  const commentOnTask = useAppStore((s) => s.commentOnTask)
  const startWatcher = useAppStore((s) => s.startWatcher)
  const stopWatcher = useAppStore((s) => s.stopWatcher)
  const addConductorMessage = useAppStore((s) => s.addConductorMessage)
  const setConductorStreaming = useAppStore((s) => s.setConductorStreaming)
  const theme = useAppStore((s) => s.theme)
  const setTheme = useAppStore((s) => s.setTheme)
  const setActiveGroup = useAppStore((s) => s.setActiveGroup)
  const setActiveProject = useAppStore((s) => s.setActiveProject)

  const [toast, setToast] = useState<string | null>(null)
  const showToast = useCallback((msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }, [])

  const {
    handleAddProject,
    handleNewWorkspace,
    handleRemoveProject,
    handleRemoveGroup,
    handleRenameGroup,
  } = useWorkspaceHandlers(showToast)

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
  const { isLarge, isMedium } = useBreakpoint()

  // Manual overrides — null means "use breakpoint default"
  const [sidebarOverride, setSidebarOverride] = useState<boolean | null>(null)

  // Reset override when the breakpoint boundary changes so the layout snaps
  // back to the breakpoint default on resize.
  const prevBreakpoint = useRef({ isLarge, isMedium })
  useEffect(() => {
    const prev = prevBreakpoint.current
    if (prev.isLarge !== isLarge || prev.isMedium !== isMedium) {
      setSidebarOverride(null)
      prevBreakpoint.current = { isLarge, isMedium }
    }
  }, [isLarge, isMedium])

  // Breakpoint defaults:
  //   Large  (≥1680px): sidebar expanded, backlog shown
  //   Medium (1366–1680px): sidebar collapsed, no backlog
  //   Small  (<1366px):  sidebar collapsed
  const defaultSidebarCollapsed = !isLarge

  // Effective sidebar state — user override wins; breakpoint default is the fallback
  const sidebarCollapsed = sidebarOverride ?? defaultSidebarCollapsed

  const handleToggleSidebar = useCallback(() => {
    setSidebarOverride((prev) => !(prev ?? defaultSidebarCollapsed))
  }, [defaultSidebarCollapsed])

  const [settingsOpen, setSettingsOpen] = useState(false)
  const [newTaskOpen, setNewTaskOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
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

  // ── Workspace initial load ─────────────────────────────────────────────────
  useEffect(() => {
    fetchWorkspaces()
  }, [fetchWorkspaces])

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

      // Cmd/Ctrl+K → open command palette
      if (meta && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [selectTask, paletteOpen])

  // ── Derived state ──────────────────────────────────────────────────────────

  const agentCount = Object.keys(agents).length

  const stageCounts = useMemo(() => {
    const counts: Partial<Record<Stage, number>> = {}
    for (const task of tasks) {
      counts[task.stage] = (counts[task.stage] ?? 0) + 1
    }
    return counts
  }, [tasks])

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
      action: () => {
        setPaletteOpen(false)
        setNewTaskOpen(true)
      },
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
  ], [advanceTask, handleToggleSidebar, setTheme, setPaletteOpen])

  // ── Task move handler (drag & drop) ───────────────────────────────────────

  const handleTaskMove = useCallback(
    async (task: Task, toStage: Stage) => {
      await moveTask(task.id, task.stage, toStage, task.status === 'blocked')
    },
    [moveTask]
  )

  // ── Watcher toggle handler ─────────────────────────────────────────────────

  const handleWatcherToggle = useCallback(async () => {
    if (watcherRunning) {
      await stopWatcher()
    } else {
      await startWatcher()
    }
  }, [watcherRunning, startWatcher, stopWatcher])

  // ── Conductor send handler ─────────────────────────────────────────────────

  async function handleSendConductorMessage(
    message: string,
    imagePaths: string[],
    tempPaths: string[],
    previewUrls: string[],
  ) {
    addConductorMessage({
      id: `cm-user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
      images: previewUrls.length > 0 ? previewUrls : undefined,
    })
    setConductorStreaming(true)
    try {
      await window.debussy.conductor.send(
        message,
        imagePaths.length > 0 ? imagePaths : undefined,
        tempPaths.length > 0 ? tempPaths : undefined,
      )
    } catch (err) {
      console.error('[conductor] send failed:', err)
      setConductorStreaming(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="app-shell"
      style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}
    >
      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <Sidebar
        workspaceGroups={workspaceGroups}
        activeGroupId={activeGroupId}
        activeProjectPath={activeProjectPath}
        collapsed={sidebarCollapsed}
        onToggle={handleToggleSidebar}
        onGroupSelect={setActiveGroup}
        onProjectSelect={setActiveProject}
        onAddProject={handleAddProject}
        onRemoveProject={handleRemoveProject}
        onNewWorkspace={handleNewWorkspace}
        onRenameGroup={handleRenameGroup}
        onRemoveGroup={handleRemoveGroup}
        onSettingsClick={() => setSettingsOpen(true)}
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
            onNewTask={() => setNewTaskOpen(true)}
            onWatcherToggle={handleWatcherToggle}
            onTaskMove={handleTaskMove}
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
          agentCount={agentCount}
          lastEvent={lastEvent}
          stageCounts={stageCounts}
          onClose={() => selectTask(null)}
          onAdvance={() => selectedTaskId && advanceTask(selectedTaskId)}
          onBlock={() => selectedTaskId && blockTask(selectedTaskId)}
        >
          {selectedTask && (
            <TaskDetailBody
              task={selectedTask}
              logEntries={taskLogEntries}
              agentName={selectedAgent?.agent ?? null}
              onComment={(message) =>
                selectedTaskId && commentOnTask(selectedTaskId, message)
              }
            />
          )}
        </TaskDetailShell>
      </div>

      {/* ── Conductor panel — always visible ───────────────────────────────── */}
      <Conductor
        messages={conductorMessages}
        onSend={handleSendConductorMessage}
      />

      {/* ── Settings modal ──────────────────────────────────────────────────── */}
      <Settings
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

      {/* ── New task dialog ──────────────────────────────────────────────────── */}
      <NewTaskDialog
        isOpen={newTaskOpen}
        onClose={() => setNewTaskOpen(false)}
        onCreated={() => {
          showToast('Task created')
          fetchAll()
        }}
      />

      {/* ── Toast notification ───────────────────────────────────────────────── */}
      {toast && (
        <div
          aria-live="polite"
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 300,
            padding: '8px 16px',
            background: 'var(--t-surface)',
            border: '1px solid var(--t-border)',
            borderRadius: 'var(--t-radius-pill)',
            fontSize: 13,
            color: 'var(--t-text)',
            boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
            animation: 'toast-in 200ms var(--t-ease) both',
            whiteSpace: 'nowrap',
          }}
        >
          {toast}
        </div>
      )}

      {/* ── Command palette ─────────────────────────────────────────────────── */}
      <CommandPalette
        isOpen={paletteOpen}
        actions={paletteActions}
        onClose={() => setPaletteOpen(false)}
      />

      <style>{`
        @keyframes toast-in {
          from { opacity: 0; transform: translateX(-50%) translateY(8px); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  )
}

export default App
