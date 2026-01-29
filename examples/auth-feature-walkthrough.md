# Example: Building a User Authentication Feature

This walkthrough shows how the multi-agent system handles a typical feature from start to finish.

## Scenario

You need to add user authentication to your web app. Here's how the agents handle it.

## Step 1: Conductor Creates Planning Task

```bash
# User tells conductor what they need
# Conductor creates planning task for architect
task_id=$(bd create "Plan: User authentication with JWT" -t architecture -p 1 \
  --assign architect \
  --note "Requirements: login, logout, token refresh, password reset")
./scripts/notify-agent.sh task architect "$task_id"
```

Output: `Created bd-plan-001`

## Step 2: Architect Plans and Creates Beads

Architect picks up the planning task:

```bash
bd show bd-plan-001
bd update bd-plan-001 --status in-progress
```

Creates implementation tasks:

```bash
bd create "Implement JWT authentication middleware" -t feature -p 1
bd create "Implement login/logout endpoints" -t feature -p 1
bd create "Implement token refresh endpoint" -t feature -p 2
bd create "Implement password reset flow" -t feature -p 2

bd update bd-plan-001 --status done
```

## Step 3: Conductor Assigns to Developer

```bash
bd ready  # See available tasks
task_id=$(bd update bd-feat-002 --assign developer --status in-progress)
./scripts/notify-agent.sh task developer "$task_id"
```

## Step 4: Developer Implements

Developer picks up the task:

```bash
bd show bd-feat-002
# Reads requirements, starts implementation
```

During implementation, developer discovers a need for email sending:

```bash
# Files a new bead instead of scope-creeping
bd create "Add email service for password reset" -t feature -p 2 \
  --note "Needed for auth feature"
```

Developer finishes and marks done:

```bash
bd update bd-feat-002 --status done --label passed
bd comment bd-feat-002 "Implemented JWT auth middleware. PR: feature/bd-feat-002"
```

## Step 5: Handoff Watcher Triggers Testing

The `handoff-watcher.sh` detects the completion and automatically creates:

```
Created bd-test-003: "Test: Implement JWT authentication middleware"
Assigned to: @tester
Notified @tester
```

## Step 6: Tester Writes Tests

Tester picks up `bd-test-003`:

```bash
bd show bd-test-003
bd update bd-test-003 --status in-progress
```

Writes tests, runs them:

```bash
npm test -- --grep "auth"
# All pass
```

Marks complete with label:

```bash
bd update bd-test-003 --status done --label passed
bd comment bd-test-003 "Added 15 unit tests, 3 integration tests. Coverage: 87%"
```

## Step 7: Handoff Triggers Review

Watcher creates:

```
Created bd-rev-004: "Review: Implement JWT authentication middleware"
Assigned to: @reviewer
Notified @reviewer
```

## Step 8: Reviewer Reviews

Reviewer finds a minor issue:

```bash
# Files a bead for the issue instead of fixing directly
bd create "Refactor: Extract token validation to separate module" -t refactor -p 3 \
  --note "Token validation logic should be reusable. Not blocking merge."

# Approves the review
bd update bd-rev-004 --status done --label approved
bd comment bd-rev-004 "LGTM. Filed bd-ref-005 for minor refactor opportunity."
```

## Step 9: Handoff Triggers Integration

Watcher creates:

```
Created bd-int-006: "Merge: Implement JWT authentication middleware"
Assigned to: @integrator
Notified @integrator
```

## Step 10: Integrator Merges

```bash
bd update bd-int-006 --status in-progress

git checkout develop
git pull
git merge feature/bd-feat-002 --no-ff
npm test  # Verify all tests pass
git push

bd update bd-int-006 --status done
```

## Step 11: Handoff Closes the Pipeline

Watcher detects integration complete:

```
Closed bd-feat-002: "Implement JWT authentication middleware"
🚀 SHIPPED!
```

## Final State

```bash
bd list

bd-plan-001  done       Plan: User authentication with JWT
bd-feat-002  done       Implement JWT authentication middleware
bd-test-003  done       Test: Implement JWT authentication middleware
bd-rev-004   done       Review: Implement JWT authentication middleware
bd-int-006   done       Merge: Implement JWT authentication middleware
bd-feat-007  open       Implement login/logout endpoints              # Next in queue
bd-feat-008  open       Implement token refresh endpoint
bd-feat-009  open       Implement password reset flow
bd-email-010 open       Add email service for password reset          # Discovered work
bd-ref-005   open       Refactor: Extract token validation            # From review
```

## Key Observations

1. **Planning first** — Architect broke down requirements before implementation
2. **No scope creep** — Developer filed `bd-email-010` instead of building it during auth
3. **Clean handoffs** — Each stage auto-triggered the next
4. **Audit trail** — Every decision is in Beads
5. **Discovered work captured** — Refactor opportunity from review became a trackable task

## Timeline

```
Day 1, 9:00   - Conductor creates planning task
Day 1, 9:05   - Architect starts planning
Day 1, 9:30   - Architect creates implementation beads
Day 1, 9:35   - Conductor assigns first task to developer
Day 1, 14:00  - Developer finishes → auto-creates test task
Day 1, 14:05  - Tester starts
Day 1, 16:00  - Tests pass → auto-creates review task
Day 1, 16:05  - Reviewer starts
Day 1, 17:00  - Review approved → auto-creates integration task
Day 1, 17:05  - Integrator merges
Day 1, 17:10  - Pipeline complete, first feature shipped
```

Total time: ~8 hours of agent work, fully tracked and auditable.
