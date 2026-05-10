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
  AGENT_LOG_STOP:  'agents:log:stop',
  CONFIG_GET:      'config:get',
  CONFIG_SET:      'config:set',
  WATCHER_START:   'watcher:start',
  WATCHER_STOP:    'watcher:stop',
  WATCHER_STATUS:  'watcher:status',
  CONDUCTOR_SEND:           'conductor:send',
  CONDUCTOR_CANCEL:         'conductor:cancel',
  CONDUCTOR_NEW_SESSION:    'conductor:new-session',
  CONDUCTOR_RESPONSE_CHUNK: 'conductor:response-chunk',
  CONDUCTOR_RESPONSE_DONE:  'conductor:response-done',
  AGENT_LOG_LINE:           'agent-log:line',
  WORKSPACE_LIST:           'workspace:list',
  WORKSPACE_ADD_GROUP:      'workspace:add-group',
  WORKSPACE_ADD_PROJECT:    'workspace:add-project',
  WORKSPACE_REMOVE_PROJECT: 'workspace:remove-project',
  WORKSPACE_REMOVE_GROUP:   'workspace:remove-group',
  WORKSPACE_RENAME_GROUP:   'workspace:rename-group',
  WORKSPACE_SET_ACTIVE:     'workspace:set-active',
  DIALOG_OPEN_DIRECTORY:    'dialog:open-directory',
  APP_INFO:                 'app:info',
  SHELL_OPEN_EXTERNAL:      'shell:open-external',
  CONDUCTOR_UPLOAD_IMAGE:   'conductor:upload-image',
  CONDUCTOR_OPEN_FILE_DIALOG: 'conductor:open-file-dialog',
} as const

export type IpcChannel = typeof IPC[keyof typeof IPC]
