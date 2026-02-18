---
name: bead-workflow
description: Bead task tracking rules and status signaling for pipeline agents
---

## Status Signals

| Signal | Command | When |
|--------|---------|------|
| Claim | `--status in_progress` | Starting work |
| Success | `--status open` | Work complete (non-terminal stages) |
| Done | `--status closed` | Terminal: merge done, acceptance pass, investigation complete |
| Rejected | `--status open --add-label rejected` | Failed review or test |
| Blocked | `--status blocked` | Can't proceed, needs conductor |

## When Blocked

Always comment before setting blocked:

```
bd comment <id> "Blocked: [specific reason]"
bd update <id> --status blocked
```

## FORBIDDEN — All Agents

- NEVER use `--add-label stage:*` or `--remove-label stage:*`
- Stage transitions are owned by the watcher, not agents

## Terminal vs Non-Terminal Stages

Only these roles set `--status closed`:
- integrator (after successful merge)
- tester (after acceptance pass)
- investigator (after research or consolidation complete)

Developer and reviewer always use `--status open` on success.

## Pipeline

```
Development: stage:development → stage:reviewing → stage:merging → closed
Investigation: stage:investigating → stage:consolidating → closed
Acceptance: stage:acceptance → closed
```
