# Debussy Electron UI Design Specification

**Date:** 2026-05-10
**Status:** Validated design (post-brainstorm)

---

## 1. App Overview

Debussy Desktop is an Electron app that replaces the tmux-based workflow for managing AI coding agent pipelines. It provides a kanban board, agent monitoring, conductor AI chat, and workspace management — all built on the shared Tonale design system.

The app is a native desktop interface over the existing debussy data layer. It reads the same SQLite database and config files that the CLI uses. CLI and tmux remain as alternative interfaces — nothing is replaced, only supplemented.

---

## 2. Architecture

### Process Model

- **Electron main process:** Window creation, IPC handlers, SQLite access via better-sqlite3, watcher process management, file watchers for real-time updates.
- **React 19 renderer:** UI components, state management via Zustand 5, Tailwind CSS 4 styling with Tonale theme tokens.
- **Watcher:** The existing Python watcher process (not rewritten for v1). Electron spawns/monitors it but does not replace it.
- **Conductor:** Claude CLI process spawned on-demand with `--print` mode for streaming responses into the chat panel.

### Data Flow

```
.takt/takt.db (SQLite WAL) ──► better-sqlite3 ──► IPC ──► React state (Zustand)
.debussy/config.json ────────► fs.watch ─────────► IPC ──► React state
.debussy/watcher_state.json ─► fs.watch ─────────► IPC ──► React state
.debussy/logs/*.log ─────────► fs.watch / tail ──► IPC ──► Agent output panel
```

- Main process polls SQLite every 5 seconds for task state changes.
- File watchers on `watcher_state.json` and log files provide real-time agent updates between polls.
- Each workspace corresponds to one project directory with its own `.takt/` and `.debussy/`.

### Build Tooling

- **electron-vite 5** for build and dev server
- **TypeScript 6** across main and renderer
- **vitest 3** for unit/integration tests
- **Playwright** for end-to-end tests

---

## 3. Tech Stack (Exact Versions)

| Dependency | Version | Purpose |
|---|---|---|
| electron | 39 | Desktop shell |
| react | 19 | Renderer UI |
| tailwindcss | 4 | Styling with @theme tokens |
| zustand | 5 | State management |
| better-sqlite3 | 11 | SQLite access from main process |
| electron-vite | 5 | Build tooling |
| @tonale/ds | 0.1.0 | Shared design system tokens/components |
| typescript | 6 | Type safety |
| vitest | 3 | Unit/integration tests |
| playwright | latest | E2E tests |

---

## 4. Tonale Design System

Shared with lem (`~/dev/tonale-design-system`, `@tonale/ds` package). Debussy extends Tonale with pipeline-specific tokens.

### 4.1 Colors

**Brand gradient:** Purple `#6c5ce7` + Teal `#00cec9`

**Dark theme (default):**

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#0a0f1a` | App background |
| `--surface` | `#131829` | Cards, panels, inputs |
| `--text-primary` | `#e8edf3` | Body text |
| `--text-secondary` | `#a8b0c2` | Labels, metadata |
| `--text-muted` | `#6b7388` | Placeholders, disabled |
| `--border` | `rgba(232, 237, 243, 0.08)` | Separators, card edges |

**Light theme:**

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#ffffff` | App background |
| `--surface` | `#f7f7fb` | Cards, panels, inputs |
| `--text-primary` | `#1a1a2e` | Body text |
| `--text-secondary` | `#4a4a68` | Labels, metadata |
| `--text-muted` | `#8888a4` | Placeholders, disabled |
| `--border` | `#e8e8f0` | Separators, card edges |

**Pipeline stage colors (debussy extension):**

| Stage | Color | Token |
|---|---|---|
| Development | Purple | `#6c5ce7` |
| Review | Amber | `#d4a843` |
| Security Review | Lavender | `#b39ddb` |
| Merge | Teal | `#00cec9` |
| Done | Muted slate | `#3a4258` |
| Blocked | Soft red | `#d97070` |

### 4.2 Typography

| Role | Font | Size |
|---|---|---|
| Sans (body, UI) | Rubik | 14px base |
| Mono (IDs, code, logs) | SF Mono | 13px base |
| Labels / badges | Rubik | 11-12px |
| Headings | Rubik Medium | 15-17px |

### 4.3 Spacing and Motion

- **Grid:** 4px base unit. All spacing is multiples of 4.
- **Border radii:** 9px (small controls) / 12px (cards) / 14px (panels) / 16px (modals) / 100px (pills, avatars)
- **Easing:** `cubic-bezier(0.2, 0.8, 0.2, 1)` for all transitions
- **Durations:** Fast 0.12s (hover, focus) / Base 0.18s (slides, fades) / Slow 0.30s (panel open/close)

---

## 5. Layout

The app uses a 4-zone layout within a single window.

```
+----------+------------------------------------------+------------+
|          |  Header (52px)                           |            |
|  Left    |  Agent Bar (48px)                        |  Right     |
|  Sidebar |  ┌────────┬────────┬────────┬────────┐   |  Panel     |
|  (210px  |  │  DEV   │ REVIEW │ MERGE  │  DONE  │   | (Conductor)|
|  or 48px)|  │        │        │        │        │   |  (320px)   |
|          |  │        │        │        │        │   |            |
|          |  └────────┴────────┴────────┴────────┘   |            |
|          +------------------------------------------+            |
|          |  Bottom Panel (task detail, expandable)   |            |
+----------+------------------------------------------+------------+
```

### 5.1 Left Sidebar (210px expanded / 48px collapsed)

Top-to-bottom layout:

1. **Workspace header:** Active group name (e.g., "Work @ Visma") with dropdown switcher chevron.
2. **Project list:** Scrollable list of projects within the active group. Each row shows:
   - Status dot (green = watcher running, gray = stopped, yellow = paused)
   - Project name (truncated with ellipsis if needed)
   - Agent count badge (number of active agents, hidden if 0)
3. **Settings link:** Gear icon at bottom, opens settings modal.

**Collapsed state (48px):** Icons only — workspace icon, project icons (first letter), gear icon. Tooltip on hover shows full names.

**Workspaces** are two-level: groups contain projects.

- **Groups** represent contexts: "Work @ Visma", "Personal", "OSS". Each group is a named collection.
- **Projects** are individual git repos. Each project points to a directory on disk that contains `.takt/` and `.debussy/`.

### 5.2 Center Board

#### Header Bar (52px)

Left-aligned:
- Project name (Rubik Medium, 17px)
- Status pills: agents count (purple bg), blocked count (red bg, hidden if 0)

Right-aligned:
- Search trigger button (magnifying glass icon, `Cmd+K` hint)
- "+ New Task" button (primary gradient bg)

#### Agent Bar (48px)

Horizontal row of agent avatars, scrollable if many agents:

- Each avatar is a 32px circle with the composer initial (B = Bach, M = Mozart, etc.)
- Colored ring matches the stage color of the task the agent is working on
- Pulsing glow animation when the agent is actively processing (status = active)
- Tooltip on hover shows: agent name, role, task ID, elapsed time
- Click opens bottom panel for that agent's task with the Agent Output tab selected

#### Kanban Columns

Four primary columns, left to right:

| Column | Header Color | Contains |
|---|---|---|
| DEV | Purple `#6c5ce7` | Tasks in `development` stage |
| REVIEW | Amber `#d4a843` | Tasks in `reviewing` stage |
| MERGE | Teal `#00cec9` | Tasks in `merging` stage |
| DONE | Muted `#3a4258` | Tasks in `done` stage |

On screens >= 1920px, an optional BACKLOG column appears to the left of DEV.

**Task cards** within each column show:
- Task ID in monospace (e.g., `PRJ-3`), top-left
- Title (Rubik, 14px, max 2 lines with ellipsis)
- Agent avatar (bottom-left, 24px, with colored ring matching stage)
- Elapsed time since entering current stage (bottom-right, muted text)
- Rejection count badge (top-right, red pill, hidden if 0)

Cards are ordered by creation time within each column (newest at bottom). Cards use `--surface` background with `--border` edge, 12px radius. Subtle lift shadow on hover.

### 5.3 Bottom Panel (Task Detail)

Slides up from the bottom when a task card is clicked. Animates with the slow timing (0.30s).

#### Collapsed State (36px status strip)

When no task is selected, a thin status strip sits at the bottom:
- Text: "Watching . 4 agents . last event 12s ago" (muted text, centered)
- Clicking the strip has no effect — it is informational only

#### Expanded State

**Header (single row, 48px):**
- Task ID (monospace, bold)
- Stage badge (pill with stage color)
- Title (truncated)
- Agent badge (avatar + name)
- Elapsed time in current stage
- Rejection count (if > 0)
- Action buttons: Block, Advance (conductor-only actions, may be disabled based on permissions)
- Close button (X icon, right edge) — collapses panel back to status strip

**Body (two-column layout, fills remaining height):**

Left column (60% width):
- **Description:** Rendered markdown from the task description field. File paths are clickable (opens in default editor via Electron shell). Inline comments from agents appear below the description in a threaded format.
- **Inline comment input:** Text field at the bottom of the left column for adding comments via `takt comment`.

Right column (40% width):
- **Timeline:** Merged chronological view of stage transitions and comments. Each entry shows timestamp, actor (agent name or "conductor"), and action. Stage transitions show "DEV -> REVIEW" with colored badges.
- **"Agent Output" toggle:** Expands to show raw process log from `.debussy/logs/<agent>.log`. Monospace font, dark background, auto-scrolls to bottom. Syntax highlighting for takt commands.

On screens < 1366px, the body switches to single-column layout (description, then timeline below).

### 5.4 Right Panel (Conductor Chat, 320px)

AI chat interface for interacting with the conductor agent.

**Header (48px):**
- "Conductor" label (Rubik Medium)
- Toggle buttons: "Watcher" (shows watcher log stream) and "Agents" (shows agent list with status)

**Chat area (scrollable):**
- User messages: right-aligned, purple-tinted background (`#6c5ce7` at 15% opacity), 14px radius
- AI messages: left-aligned, `--surface` background with `--border`, 14px radius
- AI responses that execute takt commands show those commands in a styled code block (monospace, slightly indented, with a "ran command" label)
- Timestamps in muted text below each message

**Input bar (bottom, 52px):**
- Text input field with placeholder "Ask the conductor..."
- Send button with brand gradient background (purple-to-teal)
- Enter to send, Shift+Enter for newline

**Conductor process:** Spawned as a Claude CLI process with `--print` mode. Responses stream token-by-token into the chat bubble. The process runs in the context of the active project directory.

---

## 6. Responsive Breakpoints

| Breakpoint | Sidebar | Conductor | Board | Task Detail |
|---|---|---|---|---|
| >= 1920px (4K / ultrawide) | 210px expanded | Always visible (320px) | All columns + backlog | 2-column (desc + timeline) |
| 1366-1919px (laptop) | 48px icons only | Hidden, `Cmd+\` toggle | 4 columns | Single column |
| <= 1365px (small / tablet) | 48px icons | Overlay panel | Horizontal scroll | Full-width overlay |

At the smallest breakpoint, the conductor panel becomes a full-screen overlay rather than a side panel.

---

## 7. Data Sources

The Electron app reads from existing debussy data. It does not maintain its own database.

### 7.1 Task Database

**Path:** `.takt/takt.db` (SQLite, WAL mode)

Tables read:
- `tasks` — id, title, description, stage, status, tags, created_at, updated_at
- `dependencies` — task_id, depends_on
- `log` — task_id, action, actor, message, timestamp

Access via better-sqlite3 in the main process. Read-only from Electron's perspective — writes go through `takt` CLI commands executed as child processes.

### 7.2 Configuration

**Path:** `.debussy/config.json`

Fields used:
- `base_branch` — displayed in settings and board header
- `max_total_agents` — displayed in settings, used for agent bar capacity
- `paused` — reflected in watcher status indicator
- `role_models` — displayed in settings
- `test_command` — displayed in settings

### 7.3 Watcher State

**Path:** `.debussy/watcher_state.json`

Contains running agent metadata:
- `task` — task ID the agent is working on
- `role` — agent role (developer, reviewer, integrator, tester, security-reviewer)
- `name` — composer name (Bach, Mozart, etc.)
- `pid` — OS process ID
- `started_at` — ISO timestamp

File-watched for real-time updates. Changes trigger IPC events to the renderer.

### 7.4 Agent Logs

**Path:** `.debussy/logs/<agent-name>.log`

Raw stdout/stderr from each agent process. Tailed in real-time when the Agent Output view is open for a given task.

**Path:** `.debussy/logs/watcher.log`

Watcher event log. Displayed in the conductor panel's "Watcher" toggle view.

---

## 8. Process Architecture

### 8.1 Watcher Management

The existing Python watcher process is not rewritten for v1. Electron manages it as an external process:

- **Start:** Spawns `debussy watch` as a child process when the user starts the watcher from the UI.
- **Monitor:** Watches the process for exit. Reads `watcher_state.json` for agent metadata.
- **Stop:** Sends SIGTERM to the watcher process.

### 8.2 State Synchronization

```
SQLite poll (5s) ──► diff against Zustand store ──► re-render affected components
File watchers ─────► immediate IPC event ─────────► Zustand store update
```

The 5-second poll is the source of truth for task state. File watchers provide faster feedback for agent activity (start/stop/output) but do not replace the poll.

### 8.3 Command Execution

When the conductor or user issues takt commands (create, advance, block, etc.), Electron:

1. Spawns `takt <command>` as a child process in the project directory
2. Captures stdout/stderr
3. Triggers an immediate SQLite re-poll on completion
4. Updates the Zustand store

---

## 9. Interactions

### 9.1 Core Interactions

| Action | Trigger | Result |
|---|---|---|
| Select task | Click task card | Bottom panel slides up with task detail |
| View agent output | Click agent avatar in agent bar | Bottom panel opens for that agent's task, Agent Output tab selected |
| Search / command palette | `Cmd+K` | Modal overlay with search field. Search tasks, run commands (create, advance), switch workspace/project |
| Toggle conductor | `Cmd+\` | Right panel slides in/out |
| Close task detail | `Escape` or close button | Bottom panel slides down to status strip |
| Switch view | Click different project in sidebar | Board reloads for new project, bottom panel closes, conductor panel stays |
| New task | "+ New Task" button or `Cmd+K` > "create" | Inline form or modal for task creation |

### 9.2 Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd+K` | Open command palette |
| `Cmd+\` | Toggle conductor panel |
| `Escape` | Close bottom panel / dismiss modal |
| `Cmd+1-4` | Focus kanban column (DEV, REVIEW, MERGE, DONE) |
| `Cmd+,` | Open settings |

### 9.3 Drag and Drop

Not implemented for v1. Task movement is driven by the pipeline (watcher advances/rejects). Manual drag-and-drop would conflict with the state machine model.

---

## 10. Settings

Settings modal with sidebar navigation. Opens via gear icon in left sidebar or `Cmd+,`.

### 10.1 General

- **Appearance:**
  - Theme: Dark / Light / System
  - Density: Comfortable / Compact
  - Sidebar default state: Expanded / Collapsed
  - Board columns: Show/hide backlog column
  - Conductor visibility: Always visible / Toggle
- **Keyboard Shortcuts:** Rebindable shortcuts table
- **Notifications:** Desktop notifications for stage changes, agent failures, blocked tasks

### 10.2 Pipeline

- **Agents:**
  - Max agent count (maps to `max_total_agents`)
  - Agent timeout
  - Provider selection
  - Role models (maps to `role_models` in config)
- **Watcher:**
  - Poll interval (default 5s)
  - Auto-start watcher when project opens
- **Git & Branches:**
  - Base branch (maps to `base_branch`)
  - Test command override (maps to `test_command`)

### 10.3 Workspaces

- Manage workspace groups: create, rename, delete, reorder
- Manage projects within groups: add (browse for directory), remove, reorder
- Each project entry shows: name, path, watcher status

### 10.4 Advanced

- **Remote Access:** v2 feature, UI present but grayed out with "Coming in v2" label. Shows future capability: WebSocket server, Tailscale integration, thin client mode.
- **About:** App version, Electron/Node/Chrome versions, links to documentation

---

## 11. Remote Access (v2, Architecture-Ready)

Not implemented in v1, but the IPC layer is designed to support it.

### 11.1 Concept

A WebSocket server runs in the Electron main process on a Mac Mini (or similar always-on machine). A MacBook connects as a thin client, receiving the same IPC events over WebSocket instead of local IPC.

### 11.2 Network Layer

Tailscale for zero-config private networking between machines. The WebSocket server binds to the Tailscale interface only.

### 11.3 v1 Preparation

- All renderer-to-main communication goes through a typed IPC abstraction layer
- This abstraction can be swapped from Electron IPC to WebSocket without changing renderer code
- State synchronization messages are serializable (no functions, no circular refs)
- Authentication and encryption deferred to v2 design

---

## 12. State Management (Zustand)

### 12.1 Store Structure

```typescript
interface DebussyStore {
  // Workspace
  activeGroup: string;
  activeProject: string;
  groups: WorkspaceGroup[];

  // Tasks
  tasks: Task[];
  selectedTaskId: string | null;

  // Agents
  agents: AgentState[];

  // UI
  sidebarExpanded: boolean;
  conductorVisible: boolean;
  bottomPanelOpen: boolean;
  bottomPanelTab: 'description' | 'timeline' | 'output';

  // Conductor
  conductorMessages: ChatMessage[];
  conductorProcessRunning: boolean;

  // Watcher
  watcherRunning: boolean;
  watcherPaused: boolean;
  lastEvent: string | null;
}
```

### 12.2 Update Flow

1. Main process detects change (poll or file watch)
2. Main process sends typed IPC event to renderer
3. Zustand middleware receives IPC event and updates store
4. React components re-render via Zustand selectors

---

## 13. Component Hierarchy

```
<App>
  <Sidebar>
    <WorkspaceHeader />
    <ProjectList>
      <ProjectItem />
    </ProjectList>
    <SidebarFooter />
  </Sidebar>
  <MainArea>
    <BoardHeader />
    <AgentBar>
      <AgentAvatar />
    </AgentBar>
    <KanbanBoard>
      <KanbanColumn>
        <TaskCard />
      </KanbanColumn>
    </KanbanBoard>
    <BottomPanel>
      <TaskDetailHeader />
      <TaskDetailBody>
        <DescriptionPane />
        <TimelinePane />
        <AgentOutputPane />
      </TaskDetailBody>
      <StatusStrip />  <!-- collapsed state -->
    </BottomPanel>
  </MainArea>
  <ConductorPanel>
    <ConductorHeader />
    <ChatArea>
      <ChatBubble />
    </ChatArea>
    <ChatInput />
  </ConductorPanel>
  <CommandPalette />  <!-- modal overlay -->
  <SettingsModal />   <!-- modal overlay -->
</App>
```

---

## 14. File Structure

```
electron-app/
  package.json
  electron-vite.config.ts
  tsconfig.json
  src/
    main/
      index.ts              # Electron main entry, window creation
      ipc.ts                # IPC handler registration
      sqlite.ts             # better-sqlite3 wrapper for .takt/takt.db
      watcher.ts            # Watcher process spawn/monitor/stop
      conductor.ts          # Conductor Claude CLI process management
      file-watchers.ts      # fs.watch for config/state/log files
      workspace.ts          # Workspace/project directory resolution
    preload/
      index.ts              # Contextual bridge exposing IPC to renderer
    renderer/
      index.html
      main.tsx              # React entry
      store/
        index.ts            # Zustand store definition
        ipc-middleware.ts   # IPC event → store update bridge
      components/
        Sidebar/
        Board/
        BottomPanel/
        Conductor/
        CommandPalette/
        Settings/
        shared/             # Buttons, badges, pills, avatars
      hooks/
        useTasks.ts
        useAgents.ts
        useWatcher.ts
        useConductor.ts
      styles/
        tonale.css          # @theme token imports from @tonale/ds
        app.css             # App-level Tailwind utilities
  tests/
    unit/                   # vitest
    e2e/                    # playwright
```

---

## 15. Non-Goals for v1

- Rewriting the Python watcher in Node/TypeScript
- Drag-and-drop task reordering on the board
- Remote access / thin client mode (architecture-ready, not implemented)
- Mobile or web versions
- Writing to SQLite directly (all mutations go through takt CLI)
- Custom themes beyond dark/light
- Plugin system
