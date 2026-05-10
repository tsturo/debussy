# ADR-0001: Electron UI Architecture

**Date:** 2026-05-10
**Status:** Accepted

## Context

Debussy is a pipeline orchestrator for Claude Code agents. It currently runs as a CLI/tmux-based system with a Python watcher, SQLite task database (takt), and git worktree management. We are building a desktop application to provide a visual interface for managing workspaces, monitoring agent pipelines, and interacting with the conductor.

Key requirements for the desktop app:

- Spawn and manage subprocess trees (claude CLI agents, Python watcher)
- Direct SQLite database access for reading task state
- File system watching (watcher_state.json, .takt/takt.db)
- Git worktree operations
- Streaming output from CLI processes
- Future extensibility toward remote viewing

The decisions below establish the foundational architecture for the Debussy desktop application.

## Decision

### 1. Electron over Tauri

Debussy's core operations are subprocess spawning (claude CLI agents), direct SQLite access, file system manipulation, and git worktree management. Node.js handles all of these natively via `child_process` and `better-sqlite3`. Tauri would require wrapping every one of these operations through Rust IPC, adding unnecessary friction for a developer tool where the target audience already has Node.js installed. Electron's mature ecosystem and straightforward main-process model are a better fit.

### 2. Keep Python watcher for v1

The existing Python watcher (~380 lines) is proven in production. It handles agent lifecycle, spawning, timeout, and stage transitions reliably. Rewriting it in Node.js is a v2 goal. For v1, Electron spawns the watcher as a child process and monitors its output. The watcher continues to write `watcher_state.json`; Electron watches this file for UI updates. This avoids a risky rewrite and lets us ship the desktop app without changing the orchestration layer.

### 3. Read-only SQLite access from Electron

Electron reads `.takt/takt.db` via `better-sqlite3` in read-only mode. All writes go through the `takt` CLI, spawned as child processes. This avoids WAL mode write contention between Electron and the watcher/agents. SQLite WAL supports concurrent readers safely, so the UI can poll or watch for changes without interfering with the pipeline. The takt CLI remains the single writer, preserving the existing concurrency model.

### 4. Tonale shared design system

The design system is imported as a `@tonale/ds` git dependency. It provides CSS tokens, a theme system, and shared React components. App-specific components (KanbanCard, AgentAvatar, etc.) stay in the debussy `desktop/` directory and consume Tonale tokens. This ensures visual consistency with lem and future apps that share the design system, while keeping domain-specific UI co-located with the domain logic.

### 5. Zustand over Redux

The data model is simple: tasks, agents, config, workspaces. There are no complex reducers or middleware requirements. Zustand's minimal API with selectors provides efficient re-renders without boilerplate. The store can be split into slices (tasks, agents, ui) without ceremony, and its subscribe API integrates naturally with Electron IPC for pushing state from the main process.

### 6. Conductor as on-demand Claude CLI process

Instead of maintaining a persistent Claude session, the conductor is spawned via `claude --print --system-prompt ...` when the user sends a message. Output (takt commands and explanations) is streamed back to the chat panel. This avoids the complexity of maintaining a persistent process, simplifies lifecycle management, and means a crashed conductor has no state to recover. Each invocation is stateless from the process perspective; conversation context is managed by the application.

### 7. Workspace = project directory

Each workspace maps 1:1 to a directory containing `.takt/` and `.debussy/`. Workspace groups (like "Work @ Visma") are a UI-only concept stored in Electron's app data directory. There is no unified database across workspaces. SQLite stays per-project, matching the existing CLI model. This keeps the desktop app as a view layer over the same file structure the CLI uses, so both interfaces remain interchangeable.

### 8. WebSocket API architecture-ready for remote

The IPC layer between the main process and the renderer uses a message protocol that can be extended to WebSocket for remote viewing. v1 uses Electron IPC exclusively. v2 adds a WebSocket server that speaks the same protocol, allowing a remote Electron instance or a browser client to connect. Designing the protocol now avoids a retrofit later, but we do not build the WebSocket server until there is a concrete need.

## Consequences

**Positive:**

- v1 ships without rewriting the Python watcher, reducing risk and timeline.
- Read-only SQLite access eliminates write contention entirely.
- Zustand keeps the frontend state layer small and auditable.
- The workspace-per-directory model maintains CLI/desktop interchangeability.
- The message protocol design enables remote viewing without architectural changes.
- Tonale ensures a consistent design language across applications.

**Negative:**

- Electron bundles Chromium, resulting in a larger application size (~150-200MB) compared to Tauri.
- The Python watcher as a child process means Electron must handle process lifecycle for a non-Node runtime, adding operational complexity.
- Read-only SQLite access means the UI cannot write directly; all mutations require spawning takt CLI subprocesses, adding latency to user actions.
- On-demand conductor spawning has per-invocation startup cost; if users expect instant responses, this may need revisiting.

**Deferred to v2:**

- Rewrite the Python watcher in Node.js to eliminate the Python runtime dependency.
- WebSocket server for remote viewing.
- Persistent conductor sessions if startup latency becomes a problem.
