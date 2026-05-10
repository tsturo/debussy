// IPC channel name constants shared between main and renderer processes.
// Import from this module instead of using raw strings to avoid typos.

export const IPC = {
  TASKS_LIST:      'tasks:list',
  TASK_GET:        'tasks:get',
  TASK_ADVANCE:    'tasks:advance',
  TASK_BLOCK:      'tasks:block',
  TASK_COMMENT:    'tasks:comment',
  TASK_CREATE:     'tasks:create',
  AGENTS_LIST:     'agents:list',
  AGENT_LOG:       'agents:log',
  CONFIG_GET:      'config:get',
  CONFIG_SET:      'config:set',
  WATCHER_START:   'watcher:start',
  WATCHER_STOP:    'watcher:stop',
  WATCHER_STATUS:  'watcher:status',
  CONDUCTOR_SEND:  'conductor:send',
  CONDUCTOR_STREAM: 'conductor:stream',
} as const

export type IpcChannel = typeof IPC[keyof typeof IPC]
