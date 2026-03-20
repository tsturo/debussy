# Takt Multi-Project Support

## Problem

A single debussy instance manages all tasks under one prefix (e.g. `PKL-1`, `PKL-2`). When work spans different concerns — a main feature, PR fixes, an unrelated enhancement — task IDs interleave confusingly. There's no way to visually distinguish or filter tasks by effort.

## Goals

- Separate ID namespaces per effort (e.g. `PKL-*` for feature, `FIX-*` for hotfix)
- Filter tasks by project on board and list
- One shared pipeline, branch, and database — no isolation
- Backward compatible with existing single-prefix usage

## Non-Goals

- Per-project branches or pipeline isolation
- Per-project config (agent limits, timeouts, etc.)
- Transitive project dependencies

## Design

### Schema: `projects` table

```sql
CREATE TABLE projects (
    prefix TEXT PRIMARY KEY CHECK(length(prefix) BETWEEN 2 AND 5),
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    next_seq INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX idx_projects_default ON projects(is_default) WHERE is_default = 1;
```

The `metadata` table loses the `prefix` and `next_seq` keys. They move into `projects`.

### Migration (SCHEMA_VERSION 2 → 3)

Bump `SCHEMA_VERSION` to 3. In `_migrate()`, gate on version. The entire migration runs inside `BEGIN IMMEDIATE ... COMMIT` as a single atomic block. `SCHEMA_VERSION` is updated only inside this transaction, so a crash mid-migration leaves the DB at version 2 and retries cleanly on next open.

1. `BEGIN IMMEDIATE`
2. Create `projects` table
3. Read `prefix` and `next_seq` from `metadata`
4. Insert as first project row with `is_default=1`
5. Delete `prefix` and `next_seq` from `metadata`
6. Update `SCHEMA_VERSION` to 3
7. `COMMIT`

Existing tasks are untouched — their IDs already contain the prefix.

### Affected existing functions

**`get_prefix()`**: Rewrite to query `projects` table for the row where `is_default=1`. Returns that prefix. Stays in the public API (`__init__.py` export). If no default project exists (should not happen after migration/init), raises an error — no silent fallback to "TSK".

**`_ensure_prefix()`**: Replace with `_ensure_default_project()`. Called from `get_db()` in place of `_ensure_prefix()`. On first run (no rows in `projects` table), derives a prefix via `_derive_prefix()`, inserts it as the default project with `next_seq=1`. On subsequent runs, no-op.

**`takt prefix` CLI command**: Keep as a deprecated alias. Prints a deprecation warning, then delegates to `takt project default`. This avoids breaking agent prompts and scripts. The `takt init` output message is updated to reference `takt project default`. CLAUDE.md command reference updated.

**`generate_id()`**: See next section.

### ID Generation

`generate_id()` changes:
- Accepts optional `prefix` parameter
- If `prefix` is None, uses the default project
- Atomically increments `next_seq`: `UPDATE projects SET next_seq = next_seq + 1 WHERE prefix = ? RETURNING next_seq - 1` (the returned value is the seq to use). This prevents duplicate IDs under concurrent access.
- Errors if prefix not found

### CLI: `takt project` subcommand

```
takt project add <PREFIX> <NAME> [--default]
takt project list
takt project default <PREFIX>
takt project rm <PREFIX>
```

**`add`**: Validates prefix (2-5 uppercase letters), inserts row. If `--default` or no other projects exist, sets as default. If adding a prefix that matches existing task IDs (from before multi-project), scans for max existing sequence number via `CAST(SUBSTR(id, LENGTH(prefix) + 2) AS INTEGER)` and sets `next_seq` to `max + 1` to avoid ID collisions. Non-numeric suffixes are ignored in the scan.

**`list`**: Shows all projects with task counts and which is default.

**`default`**: Switches the default project. Exactly one project is default at all times. Implementation must unset old default and set new default in a single transaction (partial unique index enforces at most one `is_default=1`).

**`rm`**: Removes a project only if no tasks use that prefix. Match rule: `id LIKE '{prefix}-%'` (exact prefix followed by dash). Cannot remove the default project (switch default first).

### Task creation

```
takt create "title" [-p PREFIX] [-d "description"]
```

`-p` / `--project` specifies the project prefix. Omit to use default. Errors if prefix not found ("project FIX not found, create it first with `takt project add`").

### Task listing and board

```
takt list [-p PREFIX]
debussy board [-p PREFIX]
```

`-p` filters to tasks whose ID starts with the given prefix (`id LIKE '{prefix}-%'`). Omit to show all. `list_tasks()` gains an optional `prefix` parameter for this. `cmd_board` in `board.py` and its argparse definition in `__main__.py` must accept and forward `-p`.

### Public API surface

Project management is CLI-only. No new exports in `__init__.py` beyond the existing `get_prefix()` (rewritten). `generate_id()` gains the optional `prefix` param — already exported.

### Conductor workflow

1. Conductor starts a new effort
2. Checks if a suitable project exists (`takt project list`)
3. If not, suggests a prefix + name to the user
4. User approves or tweaks
5. `takt project add PKL "Pickle feature" --default`
6. Creates tasks normally — they get the default prefix

For subsequent efforts: conductor decides same project or new one. New project = same suggest-and-confirm flow.

### Cross-project dependencies

Dependencies can reference any task ID regardless of prefix. `FIX-1` can depend on `PKL-3`. No restrictions.

### Prefix derivation

`_derive_prefix()` still exists for the initial auto-setup (first run with no projects). After that, projects are explicit.

## What Doesn't Change

- `tasks` table schema (no project column — prefix is in the ID)
- `dependencies`, `log` tables
- Pipeline stages, statuses, transitions
- Watcher, agents, spawner
- Branch model (single `base_branch`)
- `.debussy/config.json` structure

## Testing

- Migration: existing DB with metadata prefix/next_seq migrates correctly
- ID generation: respects per-project sequence counters
- CLI: add, list, default, rm — happy paths and error cases
- Create with `-p`: uses specified project, errors on unknown
- Cross-project deps work
- Default enforcement: exactly one default at all times
