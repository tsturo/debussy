# Debussy Workflow Guide

## Starting the System

```bash
./scripts/start.sh
```

This creates a tmux session with:
- **watcher** - Monitors mailboxes, spawns agents on demand
- **conductor** - Your interface to the system
- **status** - Live system status

## Talking to Conductor

In the conductor window, start Claude with:
```
Run as @conductor. [your requirement]
```

Examples:
```
Run as @conductor. I need user authentication with JWT tokens.
Run as @conductor. Add a REST API for managing products.
Run as @conductor. Fix the bug where login fails on mobile.
```

## What Happens

### 1. Planning Phase

Conductor creates a planning task:
```bash
./scripts/orchestra delegate "User authentication with JWT"
```

This:
- Creates a bead for the architect
- Sends a message to architect's mailbox
- Watcher detects the message and spawns @architect

Architect:
- Analyzes the requirement
- Creates implementation beads
- Notifies conductor when done

### 2. Assignment Phase

Conductor checks for ready tasks:
```bash
bd ready
```

Assigns to developers:
```bash
./scripts/orchestra assign bd-001 developer
./scripts/orchestra assign bd-002 developer2
```

### 3. Implementation Phase

When developer receives task:
- Watcher spawns a Claude instance
- Developer creates feature branch: `feature/bd-001-auth`
- Implements the feature
- Commits with bead reference: `[bd-001] Add auth service`
- Marks bead done and notifies conductor

### 4. Pipeline Phase

Handoff watcher automatically creates:
- **Test task** → spawns @tester
- **Review task** → spawns @reviewer
- **Integration task** → spawns @integrator

Each agent:
- Spawns when they have mail
- Does their work
- Notifies conductor
- Exits when done

## Monitoring Progress

### Status Window
The status window auto-refreshes every 5 seconds showing:
- Mailbox counts for each agent
- In-progress beads
- Ready beads

### Manual Checks
```bash
# System status
./scripts/orchestra status

# Check conductor inbox for responses
./scripts/orchestra inbox

# Check beads
bd list
bd ready
```

## Git Workflow

### Branch Naming
```
feature/bd-xxx-short-description
bugfix/bd-xxx-short-description
hotfix/bd-xxx-short-description
```

### Commit Format
```
[bd-xxx] Brief description

- Detail 1
- Detail 2
```

### Flow
```
main
└── develop
    ├── feature/bd-001  ← developer works here
    ├── feature/bd-002  ← another developer
    └── feature/bd-003
```

Integrator merges to develop, then to main for releases.

## Mailbox System

### How It Works

Each agent has an inbox:
```
.claude/mailbox/
├── conductor/
│   └── inbox/           # Responses from agents
├── architect/
│   └── inbox/           # Planning tasks
├── developer/
│   └── inbox/           # Implementation tasks
└── ...
```

Messages are JSON files sorted by priority and timestamp.

### Sending Messages
```bash
# Conductor sends to agent
./scripts/orchestra notify developer "Please prioritize bd-001"

# Agent sends to conductor
python -m debussy send conductor "Completed bd-001" "Details..."
```

## Agent Lifecycle

1. **Idle** - No messages in mailbox
2. **Spawned** - Watcher detects message, starts Claude
3. **Working** - Agent processes task
4. **Done** - Agent notifies conductor, exits
5. **Idle** - Back to waiting

Agents don't run continuously. They spawn when needed.

## Commands Reference

### Orchestra CLI
```bash
./scripts/orchestra delegate "requirement"  # Plan with architect
./scripts/orchestra assign bd-xxx agent     # Assign bead
./scripts/orchestra status                  # System status
./scripts/orchestra inbox                   # Check responses
./scripts/orchestra notify agent "msg"      # Send message
./scripts/orchestra broadcast "msg"         # Message all agents
./scripts/orchestra init                    # Initialize mailboxes
```

### Beads Commands
```bash
bd ready                          # Show unblocked tasks
bd list                           # All tasks
bd list --status in-progress      # In progress
bd show bd-xxx                    # Task details
bd create "title" -t feature -p 2 # Create task
bd update bd-xxx --status done    # Update status
```

## Troubleshooting

### Agent Not Spawning
```bash
# Check if message is in mailbox
python -m debussy check developer

# Check watcher is running
tmux select-window -t debussy:watcher
```

### Watcher Crashed
```bash
# Restart watcher
tmux select-window -t debussy:watcher
python -m debussy watch
```

### Start Fresh
```bash
# Kill session and restart
tmux kill-session -t debussy
./scripts/start.sh
```

## Tips

1. **Talk only to conductor** - Don't interact with other agents directly
2. **Check inbox regularly** - Agents send completion notifications
3. **Monitor status** - Keep the status window visible
4. **Use beads** - All work should be tracked
5. **Feature branches** - All code on branches, never main
