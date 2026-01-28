# Multi-Agent Workflow Guide

## Setup (One-time)

### 1. Install Beads
```bash
# macOS
brew install beads

# Linux/manual
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
```

### 2. Initialize in Your Project
```bash
cd your-project
bd init
bd setup claude
```

### 3. Copy Subagent Definitions
```bash
mkdir -p .claude/subagents
# Copy architect.md, tester.md, documenter.md, reviewer.md to .claude/subagents/
```

### 4. Copy CLAUDE.md
```bash
# Copy CLAUDE.md to your project root
```

---

## Daily Workflow

### Starting Work

Always start with the conductor:

```bash
claude
# "Run as @conductor. Here's my requirement: [your requirement]"
```

The conductor will:
1. Delegate planning to @architect (and @designer if UI work)
2. Wait for beads to be created
3. Assign tasks from `bd ready`

### Execution Options

**Option A: Fully Automated (Recommended)**

**Terminal 1 - Handoff Watcher**
```bash
./scripts/handoff-watcher.sh watch
```

**Terminal 2 - Conductor**
```bash
claude
# "Run as @conductor. Here's my requirement: [your requirement]"
```

**Terminals 3-6 - Workers**
```bash
claude --resume
# "Run as @developer. Check bd ready for tasks assigned to me."
```

### Option B: Semi-Automated

Run handoff checks manually when agents complete work:
```bash
# After any task completes
./scripts/handoff.sh  # Interactive mode

# Or direct commands
./scripts/handoff.sh to-test bd-feat-123
./scripts/handoff.sh to-review bd-test-456
```

### Option C: Manual (Learning Mode)

Good for understanding the system before automating.

### Morning: Plan the Day

**Always start with conductor:**
```bash
claude
# "Run as @conductor. Here's what I need: [requirement]"
```

**If continuing existing work:**
```bash
claude
# "Run as @conductor. Check bd ready and assign tasks."
```

### Working: Main Session + Subagents

**Terminal 1 - Main Session (Conductor)**
```bash
claude
# "I'm working on the auth module. Let me check bd ready first."
# Main session coordinates and delegates
```

**Terminal 2 - Architect Review (Background)**
```bash
claude --resume
# "Run as @architect subagent. Review the auth module and file beads for issues."
```

**Terminal 3 - Tester (Background)**
```bash
claude --resume  
# "Run as @tester subagent. Write tests for UserService. Check bd ready for your tasks."
```

### Using tmux (Recommended)

```bash
# Start tmux session
tmux new -s agents

# Split into panes
Ctrl-b %    # Split vertical
Ctrl-b "    # Split horizontal

# Navigate panes
Ctrl-b arrow-key

# Layout for 4 agents:
# ┌─────────────┬─────────────┐
# │   Main      │  Architect  │
# ├─────────────┼─────────────┤
# │   Tester    │  Documenter │
# └─────────────┴─────────────┘
```

### End of Day: Land the Plane
```bash
# In each session, tell Claude:
# "Let's land the plane. Update beads status and summarize."

# Then check overall status
bd stats
bd ready  # See what's next for tomorrow
```

---

## Automated Pipeline

### Pipeline Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PLANNING PHASE                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────┐    ┌─────────────┐    ┌────────────────────┐    ┌───────┐ │
│  │ user │───▶│ @conductor│───▶│@architect +@designer│───▶│ beads │ │
│  └──────┘    └─────────────┘    └────────────────────┘    └───────┘ │
│                     │                                          │     │
│                     └──────────── assigns from bd ready ◀──────┘     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        EXECUTION PHASE                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐       │
│  │ feature │───▶│  test   │───▶│ review  │───▶│ integration │       │
│  │ (dev)   │    │(tester) │    │(reviewer│    │ (integrator)│       │
│  └─────────┘    └────┬────┘    └────┬────┘    └──────┬──────┘       │
│                      │              │                 │              │
│                      ▼              ▼                 ▼              │
│                  ┌───────┐    ┌──────────┐      ┌─────────┐         │
│                  │failed │    │ changes  │      │  docs   │         │
│                  │→ dev  │    │requested │      │(parallel)│        │
│                  └───────┘    │ → dev    │      └─────────┘         │
│                               └──────────┘                           │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        BUG FIX PIPELINE                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  P1 (Critical):   bug ──────────────────────────▶ integration        │
│                   (fast track, skip test/review)                     │
│                                                                      │
│  P2-P5 (Normal):  bug ───▶ test ───▶ review ───▶ integration        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Handoff Triggers

| When this completes... | Automation creates... | Assigns to |
|------------------------|----------------------|------------|
| `planning` (done) | Tasks in `bd ready` | @conductor assigns |
| `feature` (done) | `test: [title]` | @tester |
| `test` (done, passed) | `review: [title]` | @reviewer |
| `test` (done, failed) | `bug: fix [title]` | @developer |
| `review` (approved) | `integration: [title]` + `docs: [title]` | @integrator, @documenter |
| `review` (changes requested) | Updates parent → in-progress | @developer |
| `bug` P1 (done) | `integration: hotfix` | @integrator |
| `bug` P2+ (done) | `test: [title]` | @tester |
| `integration` (done) | Closes parent task | - |

### Using the Handoff Scripts

**Automatic mode (recommended):**
```bash
# Start watcher in dedicated terminal
./scripts/handoff-watcher.sh watch

# It will automatically:
# - Poll for completed tasks every 30 seconds
# - Create appropriate follow-up tasks
# - Assign to correct agents
# - Log all actions to logs/handoffs.log
```

**Manual mode:**
```bash
# Interactive
./scripts/handoff.sh

# Direct commands
./scripts/handoff.sh to-test bd-feat-123      # Feature done → Test
./scripts/handoff.sh to-review bd-test-456    # Test passed → Review
./scripts/handoff.sh test-failed bd-test-456  # Test failed → Fix
./scripts/handoff.sh to-integration bd-rev-789 # Approved → Merge
./scripts/handoff.sh complete bd-int-999       # Merged → Close
```

### Labels for Pipeline Decisions

Add labels to tasks to guide automation:

```bash
# Test results
bd update bd-test-123 --label passed
bd update bd-test-123 --label failed

# Review results
bd update bd-rev-456 --label approved
bd update bd-rev-456 --label changes-requested
```

---

## Coordination Patterns

### Pattern 1: Sequential Handoff
```
Main creates task → Developer implements → Tester tests → Reviewer reviews → Integrator merges
```

```bash
# Main creates
bd create "Implement payment service" -p 1

# After implementation, create review task
bd create "Review payment service" -p 1 --blocks bd-pay1

# After review passes, testing
bd create "Test payment service" -p 1 --blocks bd-rev1

# After tests pass, docs
bd create "Document payment API" -p 2 --blocks bd-test1
```

### Pattern 2: Parallel Work
```
Main coordinates
├── Architect reviews module A
├── Tester tests module B  
└── Documenter docs module C
```

```bash
# Create independent tasks
bd create "Review: auth module" -p 2 --assign architect
bd create "Test: user module" -p 2 --assign tester
bd create "Docs: API reference" -p 3 --assign documenter

# Each agent picks up their work via bd ready
```

### Pattern 3: Swarm on Single Task
```
Complex task → Multiple agents collaborate
```

```bash
# Create parent epic
bd create "Epic: Refactor database layer" -p 1

# Subagents create subtasks as they discover work
# Architect: bd create "Extract repository pattern" --parent bd-epic1
# Tester: bd create "Add integration tests for repos" --parent bd-epic1
# Reviewer: bd create "Security review of queries" --parent bd-epic1
```

### Pattern 4: Full Pipeline (Recommended for Teams)
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Developer 1 │    │ Developer 2 │    │ Developer 3 │
│ feature/auth│    │ feature/pay │    │ feature/ntf │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                    @tester                          │
│            (tests each feature branch)              │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   @reviewer                         │
│              (reviews each branch)                  │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  @integrator                        │
│     (merges to develop, resolves conflicts)         │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
                       main
```

```bash
# Developers work on separate branches
bd create "Implement auth" -p 1 --assign dev1 --branch feature/auth
bd create "Implement payments" -p 1 --assign dev2 --branch feature/payments

# When dev work is done, tester picks up
bd create "Test auth feature" -p 1 --blocks bd-auth --assign tester

# After tests pass, reviewer
bd create "Review auth PR" -p 1 --blocks bd-auth-test --assign reviewer

# Finally, integrator merges
bd create "Merge auth to develop" -p 1 --blocks bd-auth-review --assign integrator
```

---

## The Conductor Role

The @conductor is your single entry point. Talk to conductor first, always.

**Conductor DOES:**
- Receive requirements from user
- Delegate planning to @architect and @designer
- Assign tasks from `bd ready` after planning
- Monitor progress and handle blockers
- Manage the execution pipeline

**Conductor does NOT:**
- Write code
- Make technical decisions (delegates to @architect)
- Define UX (delegates to @designer)

### Running the Conductor

**Dedicated terminal:**
```bash
claude
```

**Initial prompt (new work):**
```
Run as @conductor. Here's my requirement: [describe what you need]
```

**Initial prompt (continuing):**
```
Run as @conductor. Check bd ready and assign tasks.
```

### Conductor Commands

```bash
# See what needs assignment
bd ready

# See what's in progress
bd list --status in-progress

# See blockers
bd list --status blocked

# Assign a task
bd update bd-xxx --assign developer --status in-progress

# Check pipeline status
./scripts/handoff-watcher.sh status

# View handoff logs
tail -f logs/handoffs.log
```

### When to Intervene

The conductor should step in when:

1. **Task stuck > 2 hours** - Reassign or break into smaller tasks
2. **Pipeline backup** - Too many reviews pending? Prioritize @reviewer
3. **Conflicts** - Two developers touching same files? Sequence their work
4. **Escalation** - Technical disagreement? Assign to @architect

---

## Recommended Terminal Layout

Using tmux for full setup:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HANDOFF WATCHER                             │
│  ./scripts/handoff-watcher.sh watch                                 │
├───────────────────────────────────┬─────────────────────────────────┤
│          @COORDINATOR             │          @DEVELOPER 1           │
│  (assigns work, monitors)         │  (feature work)                 │
├───────────────────────────────────┼─────────────────────────────────┤
│          @DEVELOPER 2             │          @TESTER                │
│  (feature work)                   │  (writes tests)                 │
├───────────────────────────────────┼─────────────────────────────────┤
│          @REVIEWER                │          @INTEGRATOR            │
│  (code review)                    │  (merges)                       │
└───────────────────────────────────┴─────────────────────────────────┘
```

**tmux setup script:**
```bash
#!/bin/bash
SESSION="agents"

tmux new-session -d -s $SESSION

# Top pane - handoff watcher
tmux send-keys "./scripts/handoff-watcher.sh watch" C-m

# Split for conductor
tmux split-window -v
tmux send-keys "claude" C-m

# Split for developers
tmux split-window -h
tmux send-keys "claude --resume" C-m

tmux select-pane -t 1
tmux split-window -h
tmux send-keys "claude --resume" C-m

# More panes as needed...

tmux attach-session -t $SESSION
```

---

## Commands Quick Reference

### Beads Commands
```bash
bd ready              # Show unblocked tasks
bd stats              # Project overview
bd create "title" -p 1 # Create task (priority 1-5)
bd show bd-xxx        # Show task details
bd update bd-xxx --status done  # Update status
bd list               # List all tasks
bd list --status in-progress    # Filter by status
```

### Task Status Values
- `open` - Not started
- `in-progress` - Being worked on
- `blocked` - Waiting on something
- `done` - Completed
- `wont-fix` - Declined

### Priority Levels
- `1` - Critical / Do today
- `2` - High / Do this week
- `3` - Medium / Do this sprint
- `4` - Low / Backlog
- `5` - Nice to have

---

## Troubleshooting

### Agent Not Seeing Beads
```bash
# Sync the cache
bd sync

# Or reimport
bd import -i .beads/issues.jsonl
```

### Merge Conflicts in .beads/
```bash
# Beads handles this automatically via hash IDs
# If issues, run:
bd repair
```

### Agent Going Off-Track
```
# In Claude session:
"Stop. Run bd ready and pick up the highest priority task. 
Don't create new work without checking what's already there."
```

### Too Many Open Tasks
```bash
# Review and close stale tasks
bd list --status open --since 7d
# Close ones no longer relevant
bd update bd-xxx --status wont-fix --reason "No longer needed"
```

---

## Tips for Success

1. **Start small** - Begin with 2 parallel sessions, not 5
2. **Check bd ready often** - It's your source of truth
3. **File beads liberally** - Small tasks are easier to track
4. **Land the plane daily** - Don't leave work in limbo
5. **Trust the system** - Let Beads manage state, don't use markdown TODOs
