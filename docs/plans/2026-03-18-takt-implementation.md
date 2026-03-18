# Takt — Implementation Plan

## Goal

Replace the external `bd` (beads/Dolt) task management backend with takt, a built-in SQLite-based task system purpose-built for debussy. Eliminates Dolt server instability under parallel agent load. After implementation, debussy has zero external dependencies for task management.

## Architecture Decisions

- **SQLite with WAL mode** over Dolt/JSONL — file-based, no server, concurrent reads, crash-safe
- **Two-field state model** (`stage` + `status`) over label-based stages — directly queryable, eliminates label juggling
- **Unified log table** over separate comments + events files — single source of truth for audit trail and metrics
- **Python API + thin CLI** — internals use direct function calls, agents use CLI
- **Dependencies as join table** — takt stores links, debussy owns resolution logic

See full spec: `docs/superpowers/specs/2026-03-18-takt-design.md`

## Phase Breakdown

### Phase 1: Takt Core Module

Foundation — the SQLite database, models, and Python API. No debussy changes.

#### Bead: "Create takt database layer"
- **Files**: `src/debussy/takt/__init__.py`, `src/debussy/takt/db.py`
- **Description**: Create the takt package. `db.py` manages SQLite connections: WAL mode setup, busy timeout (5s), schema creation (tasks, dependencies, log tables with all indexes), and a `get_connection(project_dir)` context manager. `__init__.py` re-exports the public API (empty for now, will be populated as models.py and log.py are built). Database stored at `.takt/takt.db` relative to project root. Include schema version tracking for future migrations.
- **Acceptance criteria**:
  - `get_connection()` returns a SQLite connection in WAL mode
  - Schema creates all 3 tables with correct columns, constraints, and indexes per the design spec
  - Calling `get_connection()` twice on the same db works (no locking issues)
  - `.takt/` directory is auto-created if missing
- **Test criteria**: Test schema creation, WAL mode verification, concurrent read access, busy timeout behavior

#### Bead: "Create takt task model"
- **Files**: `src/debussy/takt/models.py`
- **Description**: Implement task CRUD and query functions. Functions: `create_task(db, title, description='', tags=None, deps=None) -> dict` (generates ID like `takt-<6char-hash>`, inserts task + dependencies), `get_task(db, task_id) -> dict | None` (returns task with deps list), `list_tasks(db, stage=None, status=None, tag=None) -> list[dict]` (filtered query, tag filters via json_each), `update_task(db, task_id, **fields) -> dict` (updates any mutable field, auto-updates updated_at). Task dict includes: id, title, description, stage, status, tags (as Python list), rejection_count, created_at, updated_at, dependencies (list of dep IDs). All functions take a db connection as first arg.
- **Acceptance criteria**:
  - `create_task` returns a dict with generated ID matching `takt-XXXXXX` pattern
  - `create_task` with deps creates entries in dependencies table
  - `get_task` returns None for nonexistent ID
  - `list_tasks` with stage/status/tag filters returns correct subsets
  - `update_task` modifies fields and updates `updated_at`
  - Tags stored as JSON, returned as Python list
- **Depends on**: "Create takt database layer"
- **Test criteria**: Full CRUD cycle, dependency creation/reading, filter combinations, nonexistent ID handling

#### Bead: "Create takt log and workflow operations"
- **Files**: `src/debussy/takt/log.py`
- **Description**: Implement the unified log table operations and workflow functions. Log functions: `add_comment(db, task_id, author, message)`, `add_log(db, task_id, type, author, message)` (generic log entry), `get_log(db, task_id, type=None) -> list[dict]` (filtered by type if given). Workflow functions that auto-log transitions: `advance_task(db, task_id, to_stage=None)` (computes next stage from NEXT_STAGE map, moves stage, sets status=pending, logs transition), `reject_task(db, task_id, author=None)` (increments rejection_count, moves stage to development+pending, or blocks if count>=3, logs), `claim_task(db, task_id, agent)` (sets status=active, logs assignment), `release_task(db, task_id)` (sets status=pending, logs), `block_task(db, task_id)` (sets status=blocked, logs). `get_unresolved_deps(db, task_id) -> list[str]` (returns dep IDs where stage != 'done'). Import stage constants and NEXT_STAGE/SECURITY_NEXT_STAGE maps — define them here or in a shared constants location within takt.
- **Acceptance criteria**:
  - `advance_task` moves stage correctly through the full pipeline
  - `advance_task` routes security-tagged tasks through security_review
  - `reject_task` increments counter and returns to development
  - `reject_task` blocks after 3 rejections
  - `claim_task` sets status=active, `release_task` sets status=pending
  - All workflow ops create log entries with correct type/author/message
  - `get_log` with type filter returns only matching entries
  - `get_unresolved_deps` returns IDs of deps not in stage=done
- **Depends on**: "Create takt task model"
- **Test criteria**: Full stage progression, security routing, rejection counter with auto-block, log entry verification, dependency resolution

#### Bead: "Create takt CLI"
- **Files**: `src/debussy/takt/cli.py`
- **Description**: Thin argparse CLI that wraps the Python API. Subcommands: `takt init` (creates .takt/takt.db), `takt create "title" -d "desc" [--deps id1,id2] [--tags t1,t2]`, `takt show <id> [--json]` (human-readable by default, JSON with flag), `takt list [--stage X] [--status Y] [--json]`, `takt advance <id> [--to stage]`, `takt reject <id>`, `takt claim <id> --agent <name>`, `takt release <id>`, `takt block <id>`, `takt comment <id> "message" [--author name]`, `takt log <id> [--type transition|comment|assignment]`. Human-readable output: clean columnar format for list, key:value for show. JSON output: same dict structure as Python API. Register as console_scripts entry point in pyproject.toml. CLI detects project root by walking up to find `.takt/` or `.git/`.
- **Acceptance criteria**:
  - All subcommands parse args correctly and call the right Python API function
  - `--json` flag produces valid JSON output
  - Human-readable output is clean and scannable
  - Exit code 0 on success, 1 on error with stderr message
  - `takt init` creates `.takt/takt.db` with full schema
  - Works from any subdirectory of the project (finds project root)
- **Depends on**: "Create takt log and workflow operations"
- **Test criteria**: CLI arg parsing, JSON output format, error handling for missing IDs

#### Bead: "Register takt entry point and test end-to-end"
- **Files**: `pyproject.toml`, `tests/test_takt.py`
- **Description**: Add `takt = "debussy.takt.cli:main"` to `[project.scripts]` in pyproject.toml. Create comprehensive end-to-end test that exercises the full takt lifecycle: init db, create tasks with deps and tags, list/filter, claim/release, advance through stages, reject with counter, block, comment, read log, verify metrics derivable from log. Also test concurrent access: spawn multiple threads doing reads while one writes. Reinstall debussy (`pip install -e .`) to register the entry point.
- **Acceptance criteria**:
  - `takt` command is available on PATH after install
  - End-to-end test passes: full lifecycle from create → done
  - Concurrent access test passes: no locking errors with 8 reader threads + 1 writer
  - All existing debussy tests still pass (no regressions)
- **Depends on**: "Create takt CLI"
- **Test criteria**: Full lifecycle test, concurrency test, regression check

### Phase 2: Rewire Debussy Internals

Replace bd subprocess calls with takt Python API. Update state machine and pipeline logic.

#### Bead: "Update config.py constants for takt"
- **Files**: `src/debussy/config.py`
- **Description**: Replace label-based stage constants with takt stage values. Change `STAGE_DEVELOPMENT = "stage:development"` → `STAGE_DEVELOPMENT = "development"`, same for all stages. Update `STAGE_TO_ROLE`, `NEXT_STAGE`, `SECURITY_NEXT_STAGE`, `STAGE_SHORT` to use new values (no `stage:` prefix). Add `STATUS_PENDING = "pending"`, `STATUS_ACTIVE = "active"` (rename STATUS_OPEN and STATUS_IN_PROGRESS). Keep STATUS_BLOCKED. Remove STATUS_CLOSED (replaced by stage=done). Add import of takt's `init_db` for use in cli.py. Add `TAKT_DIR = ".takt"` constant.
- **Acceptance criteria**:
  - All stage constants use plain names (no `stage:` prefix)
  - STAGE_TO_ROLE, NEXT_STAGE maps updated consistently
  - No remaining references to `"stage:"` prefix in config.py
- **Test criteria**: None (constants only)

#### Bead: "Replace bead_client.py with takt imports"
- **Files**: `src/debussy/bead_client.py`
- **Description**: Rewrite bead_client.py to be a thin adapter over takt's Python API. Replace subprocess calls with direct takt function calls. `get_bead_json(bead_id)` → calls `takt.get_task(db, bead_id)`, maps takt dict to the field names the rest of debussy expects (or update callers). `get_all_beads()` → calls `takt.list_tasks(db)`. `update_bead()` → calls appropriate takt functions (`advance_task`, `claim_task`, etc. depending on what's being changed). `comment_bead()` → calls `takt.add_comment()`. `get_unresolved_deps()` → calls `takt.get_unresolved_deps()`. No more subprocess, no more timeouts, no more retries. The db connection comes from a module-level helper that finds `.takt/takt.db` in the project root. Consider whether to keep bead_client.py as the adapter or update all callers directly — keep it if it reduces diff size.
- **Acceptance criteria**:
  - All functions work without subprocess calls
  - No `import subprocess` remaining in bead_client.py
  - Return types compatible with existing callers (or callers updated)
  - No retry logic needed (direct SQLite calls don't fail transiently)
- **Depends on**: "Update config.py constants for takt"
- **Test criteria**: Update test_bead_client.py — mock takt functions instead of subprocess

#### Bead: "Simplify transitions.py for takt"
- **Files**: `src/debussy/transitions.py`
- **Description**: Rewrite the state machine to use takt's workflow functions. The core dispatch logic stays but simplifies dramatically. `_handle_advance()` → calls `takt.advance_task()` (one function call replaces label add/remove). `_handle_rejection()` → calls `takt.reject_task()` (auto-increments counter, auto-blocks after 3). `_handle_blocked()` → already just a status change. Remove `verify_single_stage()` (stages are a column, can't have duplicates). Remove `TransitionResult` dataclass (takt operations are atomic, no need to accumulate label changes). Remove `record_event()` and `EVENTS_FILE` (takt's log table replaces pipeline_events.jsonl). The `ensure_stage_transition()` function reads task via `takt.get_task()`, dispatches handler, handler calls takt workflow function directly. Much simpler flow.
- **Acceptance criteria**:
  - Stage transitions work correctly through full pipeline
  - No references to labels for stage tracking
  - No pipeline_events.jsonl writes
  - No TransitionResult / label accumulation pattern
  - Rejection counter and auto-block work via takt
  - Security routing works via takt's advance (checks tags)
- **Depends on**: "Replace bead_client.py with takt imports"
- **Test criteria**: Update test_transitions.py — test against real takt SQLite db instead of mocking subprocess

#### Bead: "Simplify pipeline_checker.py for takt"
- **Files**: `src/debussy/pipeline_checker.py`
- **Description**: Replace `bd list` subprocess calls with takt queries. `_scan_stage()` → `takt.list_tasks(db, stage=X, status='pending')` instead of subprocess bd list. `release_ready()` → query tasks in backlog stage, check deps via `takt.get_unresolved_deps()`, call `takt.advance_task()` to move to development. `reset_orphaned()` → query tasks with status=active that have no running agent, call `takt.release_task()`. `_check_dependencies()` → `takt.get_unresolved_deps()`. `_block_failed_bead()` → `takt.block_task()` + `takt.add_comment()`. Remove subprocess imports and timeout handling for bd commands.
- **Acceptance criteria**:
  - Pipeline scanning finds and spawns correct beads
  - Dependency resolution works
  - Orphan reset works
  - No subprocess calls to bd
  - Bead blocking after max failures works
- **Depends on**: "Replace bead_client.py with takt imports"
- **Test criteria**: Integration test with takt db — create tasks, verify pipeline_checker finds them correctly

#### Bead: "Update watcher.py for takt"
- **Files**: `src/debussy/watcher.py`
- **Description**: Remove `_ensure_dolt_server()` method entirely (lines 128-145) and all calls to it (in `__init__` and `run` loop). Remove the periodic dolt health check from the heartbeat. Update `__init__` to initialize takt db connection. The watcher should call `takt.init_db()` on startup to ensure the db exists. Update `_load_rejections()` / `_save_rejections()` — rejection counts now live in takt's `rejection_count` column, so these can be removed (or simplified to just read from takt). Same for `_load_empty_branch_retries()` / `_save_empty_branch_retries()` if applicable. Update any direct bead_client calls to use the new API.
- **Acceptance criteria**:
  - No dolt references in watcher.py
  - No `_ensure_dolt_server` method
  - Watcher initializes takt db on startup
  - Rejection state read from takt, not side files
  - Watcher loop runs without bd/dolt dependencies
- **Depends on**: "Simplify transitions.py for takt", "Simplify pipeline_checker.py for takt"
- **Test criteria**: Verify watcher startup doesn't call dolt, verify rejection state persists in takt

#### Bead: "Update cli.py and metrics.py for takt"
- **Files**: `src/debussy/cli.py`, `src/debussy/metrics.py`
- **Description**: In cli.py: replace `bd init` call in `cmd_clear()` with `takt.init_db()`. Remove `_upgrade_bd()` function. Remove `bd list` and `bd version` calls. Update `cmd_clear()` to nuke `.takt/` instead of `.beads/`. Update `cmd_backup()` to back up `.takt/` instead of `.beads/`. In metrics.py: replace `_load_events()` (reads pipeline_events.jsonl) with a takt log query. `get_log(db, type='transition')` returns all transitions. Recompute stage durations from log timestamps. The metrics display logic (`_print_metrics`, trails, averages) stays mostly the same but reads from takt log instead of JSONL.
- **Acceptance criteria**:
  - `debussy clear` creates fresh takt db
  - `debussy backup` backs up .takt directory
  - `debussy metrics` reads from takt log table
  - No references to .beads, bd, or pipeline_events.jsonl
  - No `_upgrade_bd` function
- **Depends on**: "Update watcher.py for takt"
- **Test criteria**: Verify metrics output with sample takt log data

### Phase 3: Update Agent Prompts

Rewrite all agent prompts to use takt CLI commands.

#### Bead: "Update conductor prompt for takt"
- **Files**: `src/debussy/prompts/conductor.md`
- **Description**: Replace all bd commands with takt equivalents. `bd create "title" -d "desc"` → `takt create "title" -d "desc"`. `bd update <id> --add-label stage:development` → `takt advance <id> --to development`. `bd update <id> --add-label security` → `takt create ... --tags security` (set at creation) or `takt update <id> --tags '["security"]'`. `bd show <id>` → `takt show <id>`. Remove all label manipulation instructions. Update the pipeline flow description to use stage/status model instead of labels. Update command reference section.
- **Acceptance criteria**:
  - No `bd` commands remain in the prompt
  - All takt commands are syntactically correct
  - Pipeline flow description matches takt's stage/status model
  - Conductor knows how to create tasks with deps and tags
  - Conductor knows how to release tasks (advance from backlog to development)

#### Bead: "Update developer and reviewer prompts for takt"
- **Files**: `src/debussy/prompts/developer.md`, `src/debussy/prompts/reviewer.md`
- **Description**: Replace bd commands in both prompts. `bd show <BEAD_ID>` → `takt show <BEAD_ID>`. `bd update <BEAD_ID> --status in_progress` → `takt claim <BEAD_ID> --agent <AGENT_NAME>`. `bd update <BEAD_ID> --status open` → `takt release <BEAD_ID>`. `bd update <BEAD_ID> --status open --add-label rejected` → `takt reject <BEAD_ID>` (note: rejection is now a single command, no label needed). `bd update <BEAD_ID> --status blocked` → `takt block <BEAD_ID>`. `bd comment <BEAD_ID> "text"` → `takt comment <BEAD_ID> "text"`. Remove all references to label manipulation. Update any instructions about status signaling to use the new claim/release/reject/block vocabulary.
- **Acceptance criteria**:
  - No `bd` commands in either prompt
  - claim/release/reject/block used correctly
  - No label manipulation instructions
  - Agent name passed to `takt claim`

#### Bead: "Update integrator, tester, and security-reviewer prompts for takt"
- **Files**: `src/debussy/prompts/integrator.md`, `src/debussy/prompts/tester.md`, `src/debussy/prompts/security-reviewer.md`
- **Description**: Same pattern as developer/reviewer. Replace bd commands with takt equivalents. For integrator: `bd update --status closed` → `takt release <id>` (watcher handles advancing to done). For tester: same pattern. For security-reviewer: same as reviewer. Ensure all three prompts use consistent takt vocabulary. Remove label-related instructions.
- **Acceptance criteria**:
  - No `bd` commands in any of the three prompts
  - Consistent takt command usage across all prompts
  - Terminal stage handling correct (integrator/tester use release, watcher advances to done)

#### Bead: "Update visual testing prompts for takt"
- **Files**: `src/debussy/prompts/visual_web.md`, `src/debussy/prompts/visual_ios.md`, `src/debussy/prompts/visual_review_web.md`, `src/debussy/prompts/visual_test_web.md`
- **Description**: Replace any bd command references in visual testing prompt files with takt equivalents. These prompts are included as supplements to developer/reviewer prompts for frontend beads. Apply the same bd→takt substitutions: show→show, update status→claim/release/reject/block, comment→comment.
- **Acceptance criteria**:
  - No `bd` commands in any visual prompt file
  - Consistent with the main prompt updates

### Phase 4: Cleanup

Remove dead code and update documentation.

#### Bead: "Remove bd dependencies and dead code"
- **Files**: `src/debussy/bead_client.py`, `src/debussy/config.py`, `src/debussy/board.py`, `src/debussy/status.py`, `src/debussy/diagnostics.py`
- **Description**: If bead_client.py was kept as an adapter, evaluate whether to remove it and update callers to use takt directly. Remove any remaining bd/dolt references across the codebase. Remove `_ensure_dolt_server` if not already gone. Remove `pipeline_events.jsonl` references. Remove `_upgrade_bd()` from cli.py if not already done. Check board.py and status.py for any bd-specific rendering. Check diagnostics.py `comment_on_bead` — should use takt. Remove `.beads` references from `.gitignore` patterns, add `.takt`. Run `grep -r "bd " src/debussy/` and `grep -r "beads" src/debussy/` to find stragglers.
- **Acceptance criteria**:
  - `grep -r "bd show\|bd list\|bd update\|bd create\|bd comment\|bd init\|bd dolt\|bd version" src/debussy/` returns zero matches
  - `grep -r "\.beads" src/debussy/` returns zero matches (except maybe migration notes)
  - `grep -r "pipeline_events" src/debussy/` returns zero matches
  - No dead imports (subprocess used only where still needed for git/tmux)

#### Bead: "Update CLAUDE.md and documentation"
- **Files**: `CLAUDE.md`
- **Description**: Update CLAUDE.md to reflect takt replacing bd. Update the Commands section (takt commands instead of bd). Update Pipeline Flow to describe stage/status model. Update Agent sections to show takt commands. Update Project Structure to include `src/debussy/takt/`. Remove bd/beads/dolt references. Update `.beads/` → `.takt/` in directory descriptions.
- **Acceptance criteria**:
  - No `bd` command references in CLAUDE.md
  - takt commands documented accurately
  - Project structure includes takt package
  - Stage/status model described

## File Ownership Map

| File | Bead |
|------|------|
| `src/debussy/takt/__init__.py` | Create takt database layer |
| `src/debussy/takt/db.py` | Create takt database layer |
| `src/debussy/takt/models.py` | Create takt task model |
| `src/debussy/takt/log.py` | Create takt log and workflow operations |
| `src/debussy/takt/cli.py` | Create takt CLI |
| `pyproject.toml` | Register takt entry point and test end-to-end |
| `tests/test_takt.py` | Register takt entry point and test end-to-end |
| `src/debussy/config.py` | Update config.py constants for takt |
| `src/debussy/bead_client.py` | Replace bead_client.py with takt imports |
| `src/debussy/transitions.py` | Simplify transitions.py for takt |
| `src/debussy/pipeline_checker.py` | Simplify pipeline_checker.py for takt |
| `src/debussy/watcher.py` | Update watcher.py for takt |
| `src/debussy/cli.py` | Update cli.py and metrics.py for takt |
| `src/debussy/metrics.py` | Update cli.py and metrics.py for takt |
| `src/debussy/prompts/conductor.md` | Update conductor prompt for takt |
| `src/debussy/prompts/developer.md` | Update developer and reviewer prompts |
| `src/debussy/prompts/reviewer.md` | Update developer and reviewer prompts |
| `src/debussy/prompts/integrator.md` | Update integrator, tester, security-reviewer prompts |
| `src/debussy/prompts/tester.md` | Update integrator, tester, security-reviewer prompts |
| `src/debussy/prompts/security-reviewer.md` | Update integrator, tester, security-reviewer prompts |
| `src/debussy/prompts/visual_web.md` | Update visual testing prompts |
| `src/debussy/prompts/visual_ios.md` | Update visual testing prompts |
| `src/debussy/prompts/visual_review_web.md` | Update visual testing prompts |
| `src/debussy/prompts/visual_test_web.md` | Update visual testing prompts |
| `src/debussy/board.py` | Remove bd dependencies and dead code |
| `src/debussy/status.py` | Remove bd dependencies and dead code |
| `src/debussy/diagnostics.py` | Remove bd dependencies and dead code |
| `CLAUDE.md` | Update CLAUDE.md and documentation |

## Risks & Open Questions

1. **board.py and status.py** — These files render the kanban board and status display. They likely read bead data via bead_client. Need to verify they work with takt's dict format or update them.
2. **diagnostics.py** — Uses `comment_on_bead` which wraps `bd comment`. Needs updating to takt.
3. **spawner.py** — Reads bead labels/tags to decide agent type. Verify it works with takt's tag format (JSON array vs label strings).
4. **Task ID format** — Changing from `bd-XXX` / `piklr-ios-XXX` to `takt-XXXXXX`. All prompts and any ID parsing logic needs to handle the new format.
5. **Agent prompts reference `<BEAD_ID>` placeholder** — Need to decide on new placeholder name (`<TASK_ID>`?) consistently across all prompts.
6. **worktree.py** — Uses bead IDs in branch names (`feature/<bead-id>`). Need to verify it works with takt IDs or update the naming pattern.
7. **Existing tests** — test_bead_client.py and test_transitions.py mock subprocess. They need full rewrites against real takt db.
