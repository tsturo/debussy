import { useMemo } from 'react'
import type { Task, Stage, AgentRole, DebussyConfig } from '../../shared/types'
import { Header } from './Header'
import { AgentBar } from './AgentBar'
import { KanbanColumn } from './KanbanColumn'
import { STAGE_ORDER } from '../lib/stage-colors'

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
              />
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
