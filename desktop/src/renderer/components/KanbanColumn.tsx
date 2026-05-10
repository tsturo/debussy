import type { Task, Stage } from '../../shared/types'
import { STAGE_COLORS } from '../lib/stage-colors'
import { KanbanCard } from './KanbanCard'

export interface KanbanColumnProps {
  stage: Stage
  tasks: Task[]
  agents: Map<string, { name: string; stage: Stage }>
  selectedTaskId: string | null
  onCardClick: (taskId: string) => void
}

/** Column opacity by stage — done and backlog are visually de-emphasized. */
function columnOpacity(stage: Stage): number {
  if (stage === 'done') return 0.6
  if (stage === 'backlog') return 0.25
  return 1
}

export function KanbanColumn({
  stage,
  tasks,
  agents,
  selectedTaskId,
  onCardClick,
}: KanbanColumnProps) {
  const { color, label } = STAGE_COLORS[stage]

  return (
    <div
      style={{
        flex: 1,
        minWidth: '140px',
        display: 'flex',
        flexDirection: 'column',
        opacity: columnOpacity(stage),
      }}
    >
      {/* Column header: label + count on one line */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '4px',
        }}
      >
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color,
            letterSpacing: '0.04em',
            lineHeight: 1,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: 'var(--t-text-3)',
            lineHeight: 1,
          }}
        >
          {tasks.length}
        </span>
      </div>

      {/* Cards area */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          overflowY: 'auto',
          flex: 1,
        }}
      >
        {tasks.map((task) => {
          const agentInfo = agents.get(task.id) ?? null
          const agent = agentInfo
            ? { name: agentInfo.name, stage: agentInfo.stage }
            : null

          return (
            <KanbanCard
              key={task.id}
              task={task}
              agent={agent}
              isSelected={task.id === selectedTaskId}
              onClick={() => onCardClick(task.id)}
            />
          )
        })}
      </div>
    </div>
  )
}
