# Session CLI Commands

## Commands

### `debussy sessions`

List running debussy tmux sessions by querying tmux directly.

- Filter `tmux list-sessions` to `debussy-*` names
- Get project path from pane 0's `pane_current_path`
- Print table: session name + project path
- Exit 0 even if no sessions found (print "No active sessions")

### `debussy connect [name]`

Attach to a running debussy session.

- `name` is the short project name (e.g. `piklr` for `debussy-piklr`)
- If one session running and no name given: attach to it
- If multiple sessions and no name: list them, exit with hint
- Before attaching: `cd` to project path
- Error if session not found

## Implementation

### tmux.py

Add `list_debussy_sessions() -> list[dict]` returning `[{"session": str, "path": str}]`.

### cli.py

Add `cmd_sessions(args)` and `cmd_connect(args)`.

### __main__.py

Register `sessions` and `connect` subparsers.
