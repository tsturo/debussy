import { useMemo, useState, useCallback } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragStartEvent, DragEndEvent, DragOverEvent } from '@dnd-kit/core'
import type { Task, Stage, AgentRole, DebussyConfig } from '../../shared/types'
import { Header } from './Header'
import { AgentBar } from './AgentBar'
import { KanbanColumn } from './KanbanColumn'
import { KanbanCard } from './KanbanCard'
import { DragConfirmDialog } from './DragConfirmDialog'
import { STAGE_ORDER } from '../lib/stage-colors'
import { isValidMove } from '../lib/move-validation'

export interface BoardProps {
  tasks: Task[]
  agents: Array<{ taskId: string; name: string; role: AgentRole; stage: Stage; startedAt: number }>
  config: DebussyConfig | null
  selectedTaskId: string | null
  watcherRunning: boolean
  conductorVisible: boolean
  showBacklog?: boolean
  onTaskSelect: (taskId: string) => void
  onNewTask: () => void
  onWatcherToggle: () => Promise<void>
  onTaskMove: (task: Task, toStage: Stage) => Promise<void>
  onToggleConductor: () => void
}

/** Stages that are hidden when empty (not always shown as columns). */
const HIDDEN_WHEN_EMPTY: Stage[] = ['security_review', 'acceptance']

interface PendingMove {
  task: Task
  toStage: Stage
}

export function Board({
  tasks,
  agents,
  config,
  selectedTaskId,
  watcherRunning,
  conductorVisible,
  showBacklog = true,
  onTaskSelect,
  onNewTask,
  onWatcherToggle,
  onTaskMove,
  onToggleConductor,
}: BoardProps) {
  /** Group tasks by stage into a map for O(1) lookup per column. */
  const tasksByStage = useMemo(() => {
    const map = new Map<Stage, Task[]>()
    for (const stage of STAGE_ORDER) {
      map.set(stage, [])
    }
    for (const task of tasks) {
      map.get(task.stage)?.push(task)
    }
    return map
  }, [tasks])

  /** Build agents map: taskId → { name, stage } for KanbanColumn. */
  const agentsMap = useMemo(() => {
    const map = new Map<string, { name: string; stage: Stage }>()
    for (const agent of agents) {
      map.set(agent.taskId, { name: agent.name, stage: agent.stage })
    }
    return map
  }, [agents])

  /**
   * Visible stages: show all STAGE_ORDER entries except security_review and
   * acceptance when they have no tasks.
   */
  const visibleStages = useMemo(
    () =>
      STAGE_ORDER.filter(
        (stage) =>
          !HIDDEN_WHEN_EMPTY.includes(stage) ||
          (tasksByStage.get(stage)?.length ?? 0) > 0
      ),
    [tasksByStage]
  )

  // ── Drag state ──────────────────────────────────────────────────────────────

  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [overStage, setOverStage] = useState<Stage | null>(null)
  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  )

  const taskById = useMemo(() => {
    const map = new Map<string, Task>()
    for (const t of tasks) map.set(t.id, t)
    return map
  }, [tasks])

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const task = taskById.get(String(event.active.id))
      if (task) setActiveTask(task)
    },
    [taskById]
  )

  const handleDragOver = useCallback((event: DragOverEvent) => {
    const over = event.over
    setOverStage(over ? (String(over.id) as Stage) : null)
  }, [])

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setOverStage(null)
      const task = activeTask
      setActiveTask(null)

      if (!task || !event.over) return

      const toStage = String(event.over.id) as Stage
      if (!isValidMove(task.stage, task.status, toStage)) return

      setPendingMove({ task, toStage })
    },
    [activeTask]
  )

  const handleDragCancel = useCallback(() => {
    setActiveTask(null)
    setOverStage(null)
  }, [])

  const handleConfirmMove = useCallback(async () => {
    if (!pendingMove) return
    const { task, toStage } = pendingMove
    setPendingMove(null)
    await onTaskMove(task, toStage)
  }, [pendingMove, onTaskMove])

  const handleCancelMove = useCallback(() => {
    setPendingMove(null)
  }, [])

  const agentCount = agents.length
  const maxAgents = config?.max_total_agents ?? 8
  const blockedCount = tasks.filter((t) => t.status === 'blocked').length
  const projectName = config?.base_branch ?? 'debussy'

  return (
    <>
      <style>{`
        .board-backlog-col { display: flex; flex: 1; min-width: 140px; }
        .board-backlog-col--hidden { display: none !important; }
        @media (max-width: 1024px) {
          .board-backlog-col { display: none !important; }
        }
      `}</style>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}
      >
        <Header
          projectName={projectName}
          agentCount={agentCount}
          maxAgents={maxAgents}
          blockedCount={blockedCount}
          conductorVisible={conductorVisible}
          onSearchClick={() => {}}
          onNewTaskClick={onNewTask}
          onToggleConductor={onToggleConductor}
        />

        <AgentBar
          agents={agents.map((a) => ({
            taskId: a.taskId,
            name: a.name,
            role: a.role,
            stage: a.stage,
            startedAt: a.startedAt,
          }))}
          watcherRunning={watcherRunning}
          onAgentClick={onTaskSelect}
          onWatcherToggle={onWatcherToggle}
        />

        {/* Columns area wrapped in DndContext */}
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'row',
              gap: '8px',
              padding: '10px',
              overflowX: 'auto',
              overflowY: 'hidden',
            }}
          >
            {visibleStages.map((stage) => {
              const dragOver = overStage === stage && activeTask !== null
              const validTarget =
                activeTask !== null &&
                isValidMove(activeTask.stage, activeTask.status, stage)

              return (
                <div
                  key={stage}
                  className={
                    stage === 'backlog'
                      ? `board-backlog-col${showBacklog ? '' : ' board-backlog-col--hidden'}`
                      : undefined
                  }
                  style={
                    stage === 'backlog'
                      ? undefined
                      : stage === 'done'
                      ? { flex: 0.7, minWidth: '120px', display: 'flex' }
                      : { flex: 1, minWidth: '140px', display: 'flex' }
                  }
                >
                  <KanbanColumn
                    stage={stage}
                    tasks={tasksByStage.get(stage) ?? []}
                    agents={agentsMap}
                    selectedTaskId={selectedTaskId}
                    onCardClick={onTaskSelect}
                    isValidDropTarget={validTarget}
                    isDragOver={dragOver}
                  />
                </div>
              )
            })}
          </div>

          {/* Drag overlay: elevated clone of the dragged card */}
          <DragOverlay dropAnimation={null}>
            {activeTask ? (
              <KanbanCard
                task={activeTask}
                agent={agentsMap.get(activeTask.id) ? { name: agentsMap.get(activeTask.id)!.name, stage: agentsMap.get(activeTask.id)!.stage } : null}
                isSelected={false}
                onClick={() => {}}
                isDragOverlay
              />
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Confirmation dialog — rendered outside DndContext so it layers on top */}
      {pendingMove && (
        <DragConfirmDialog
          taskId={pendingMove.task.id}
          taskTitle={pendingMove.task.title}
          fromStage={pendingMove.task.stage}
          toStage={pendingMove.toStage}
          onConfirm={handleConfirmMove}
          onCancel={handleCancelMove}
        />
      )}
    </>
  )
}
