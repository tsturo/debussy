import { useMemo, useState, useCallback } from 'react'
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core'
import type { Task, Stage, AgentRole, DebussyConfig } from '../../shared/types'
import { Header } from './Header'
import { AgentBar } from './AgentBar'
import { KanbanColumn, type ActiveDragData } from './KanbanColumn'
import { DragConfirmDialog } from './DragConfirmDialog'
import { STAGE_ORDER, STAGE_COLORS } from '../lib/stage-colors'
import { useAppStore } from '../store/app-store'

export interface BoardProps {
  tasks: Task[]
  agents: Array<{ taskId: string; name: string; role: AgentRole; stage: Stage; startedAt: number }>
  config: DebussyConfig | null
  selectedTaskId: string | null
  watcherRunning: boolean
  showBacklog?: boolean
  onTaskSelect: (taskId: string) => void
  onNewTask: () => void
  onWatcherToggle: () => Promise<void>
}

interface PendingMove {
  taskId: string
  taskTitle: string
  fromStage: Stage
  toStage: Stage
  isBlocked: boolean
}

/** Stages that are hidden when empty (not always shown as columns). */
const HIDDEN_WHEN_EMPTY: Stage[] = ['security_review', 'acceptance']

export function Board({
  tasks,
  agents,
  config,
  selectedTaskId,
  watcherRunning,
  showBacklog = true,
  onTaskSelect,
  onNewTask,
  onWatcherToggle,
}: BoardProps) {
  const advanceTask  = useAppStore((s) => s.advanceTask)
  const releaseTask  = useAppStore((s) => s.releaseTask)
  const fetchAll     = useAppStore((s) => s.fetchAll)

  const [activeDragData, setActiveDragData] = useState<ActiveDragData | null>(null)
  const [activeDragTitle, setActiveDragTitle] = useState<string>('')
  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null)

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

  const agentCount = agents.length
  const maxAgents = config?.max_total_agents ?? 8
  const blockedCount = tasks.filter((t) => t.status === 'blocked').length
  const projectName = config?.base_branch ?? 'debussy'

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const data = event.active.data.current as {
      taskId: string
      taskTitle: string
      fromStage: Stage
      isBlocked: boolean
    }
    setActiveDragData({
      taskId: data.taskId,
      fromStage: data.fromStage,
      isBlocked: data.isBlocked,
    })
    setActiveDragTitle(data.taskTitle)
  }, [])

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const drag = activeDragData
    setActiveDragData(null)
    setActiveDragTitle('')

    if (!event.over || !drag) return

    const toStage = event.over.data.current?.targetStage as Stage | undefined
    if (!toStage) return

    // Validate the move
    const { fromStage, isBlocked, taskId } = drag
    if (toStage === fromStage) return
    if (fromStage === 'done') return

    const isValidMove =
      (fromStage === 'backlog' && toStage === 'development') ||
      (isBlocked && toStage === 'development') ||
      (toStage === 'backlog' && fromStage !== 'done' && fromStage !== 'backlog')

    if (!isValidMove) return

    // Find the task for its title
    const task = tasks.find((t) => t.id === taskId)
    if (!task) return

    setPendingMove({
      taskId,
      taskTitle: task.title,
      fromStage,
      toStage,
      isBlocked,
    })
  }, [activeDragData, tasks])

  const handleConfirm = useCallback(async () => {
    if (!pendingMove) return
    const { taskId, fromStage, toStage, isBlocked } = pendingMove
    setPendingMove(null)

    if (toStage === 'development') {
      if (isBlocked) {
        // Release the block first, then advance to development if not already there
        await releaseTask(taskId)
        if (fromStage !== 'development') {
          await advanceTask(taskId, 'development')
        }
      } else {
        // Backlog → Development
        await advanceTask(taskId)
      }
    } else if (toStage === 'backlog') {
      await advanceTask(taskId, 'backlog')
    }

    await fetchAll()
  }, [pendingMove, advanceTask, releaseTask, fetchAll])

  const handleCancel = useCallback(() => {
    setPendingMove(null)
  }, [])

  return (
    <>
      <style>{`
        .board-backlog-col { display: flex; flex: 1; min-width: 140px; }
        .board-backlog-col--hidden { display: none !important; }
        @media (max-width: 1024px) {
          .board-backlog-col { display: none !important; }
        }
      `}</style>

      <DndContext
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
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
            onSearchClick={() => {}}
            onNewTaskClick={onNewTask}
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

          {/* Columns area: horizontal scroll, fixed padding/gap */}
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
            {visibleStages.map((stage) => (
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
                  activeDragData={activeDragData}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Drag ghost overlay */}
        <DragOverlay>
          {activeDragData ? (
            <div
              style={{
                backgroundColor: 'var(--t-card-bg)',
                borderRadius: 'var(--t-radius-md)',
                padding: '10px 12px',
                borderLeft: `2px solid ${STAGE_COLORS[activeDragData.fromStage].color}`,
                boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
                transform: 'scale(1.02)',
                opacity: 0.92,
                minWidth: '140px',
                maxWidth: '220px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
            >
              <span style={{
                fontSize: '10px',
                fontFamily: '"SF Mono", Menlo, Monaco, Consolas, monospace',
                color: 'var(--t-text-3)',
                lineHeight: 1,
              }}>
                {activeDragData.taskId}
              </span>
              <p style={{
                fontSize: '12px',
                fontWeight: 500,
                color: 'var(--t-text)',
                margin: 0,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                lineHeight: 1.4,
              }}>
                {activeDragTitle}
              </p>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Confirmation dialog — rendered outside DndContext to avoid pointer event conflicts */}
      {pendingMove && (
        <DragConfirmDialog
          taskId={pendingMove.taskId}
          taskTitle={pendingMove.taskTitle}
          fromStage={pendingMove.fromStage}
          toStage={pendingMove.toStage}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </>
  )
}
