# Example: Building a User Authentication Feature

This walkthrough shows how Claude Crew handles a typical feature from start to finish.

## Scenario

You need to add user authentication to your web app. Here's how the crew handles it.

## Step 1: Coordinator Creates the Task

```bash
# Coordinator sees the request and creates a feature bead
bd create "Implement user authentication with JWT" -t feature -p 1 \
  --note "Requirements: login, logout, token refresh, password reset"
```

Output: `Created bd-auth-001`

## Step 2: Coordinator Assigns to Developer

```bash
bd update bd-auth-001 --assign developer --status in-progress
```

## Step 3: Developer Implements

Developer picks up the task:

```bash
bd show bd-auth-001
# Reads requirements, starts implementation
```

During implementation, developer discovers a need for email sending:

```bash
# Files a new bead instead of scope-creeping
bd create "Add email service for password reset" -t feature -p 2 \
  --note "Needed for auth feature bd-auth-001"
```

Developer finishes and marks done:

```bash
bd update bd-auth-001 --status done
bd comment bd-auth-001 "Implemented JWT auth with login, logout, refresh. Created auth middleware. PR: feature/bd-auth-001"
```

## Step 4: Handoff Watcher Triggers Testing

The `handoff-watcher.sh` detects the completion and automatically creates:

```
Created bd-test-002: "Test: Implement user authentication with JWT"
Assigned to: @tester
```

## Step 5: Tester Writes Tests

Tester picks up `bd-test-002`:

```bash
bd show bd-test-002
bd update bd-test-002 --status in-progress
```

Writes tests, runs them:

```bash
npm test -- --grep "auth"
# All pass
```

Marks complete with label:

```bash
bd update bd-test-002 --status done --label passed
bd comment bd-test-002 "Added 15 unit tests, 3 integration tests. Coverage: 87%"
```

## Step 6: Handoff Triggers Review

Watcher creates:

```
Created bd-rev-003: "Review: Implement user authentication with JWT"
Assigned to: @reviewer
```

## Step 7: Reviewer Reviews

Reviewer finds a minor issue:

```bash
# Files a bead for the issue instead of fixing directly
bd create "Refactor: Extract token validation to separate module" -t refactor -p 3 \
  --parent bd-auth-001 \
  --note "Token validation logic should be reusable. Not blocking merge."

# Approves the review
bd update bd-rev-003 --status done --label approved
bd comment bd-rev-003 "LGTM. Filed bd-ref-004 for minor refactor opportunity."
```

## Step 8: Handoff Triggers Integration + Docs

Watcher creates two tasks in parallel:

```
Created bd-int-005: "Merge: Implement user authentication with JWT"
Assigned to: @integrator

Created bd-doc-006: "Docs: Implement user authentication with JWT"
Assigned to: @documenter
```

## Step 9: Integrator Merges

```bash
bd update bd-int-005 --status in-progress

git checkout develop
git pull
git merge feature/bd-auth-001 --no-ff
npm test  # Verify all tests pass
git push

bd update bd-int-005 --status done
```

## Step 10: Handoff Closes the Pipeline

Watcher detects integration complete:

```
Closed bd-auth-001: "Implement user authentication with JWT"
🚀 SHIPPED!
```

## Step 11: Documenter Works in Parallel

Meanwhile, documenter has been updating docs:

```bash
bd update bd-doc-006 --status in-progress

# Updates README with auth setup instructions
# Adds API docs for auth endpoints
# Documents environment variables needed

bd update bd-doc-006 --status done
```

## Final State

```bash
bd list

bd-auth-001  done       Implement user authentication with JWT
bd-test-002  done       Test: Implement user authentication with JWT
bd-rev-003   done       Review: Implement user authentication with JWT
bd-int-005   done       Merge: Implement user authentication with JWT
bd-doc-006   done       Docs: Implement user authentication with JWT
bd-email-007 open       Add email service for password reset          # Discovered work
bd-ref-004   open       Refactor: Extract token validation            # From review
```

## Key Observations

1. **No scope creep** — Developer filed `bd-email-007` instead of building it during auth
2. **Clean handoffs** — Each stage auto-triggered the next
3. **Audit trail** — Every decision is in Beads
4. **Parallel work** — Docs happened alongside integration
5. **Discovered work captured** — Refactor opportunity from review became a trackable task

## Timeline

```
Day 1, 9:00   - Coordinator creates bd-auth-001
Day 1, 9:05   - Developer starts
Day 1, 14:00  - Developer finishes → auto-creates test task
Day 1, 14:05  - Tester starts
Day 1, 16:00  - Tests pass → auto-creates review task
Day 1, 16:05  - Reviewer starts
Day 1, 17:00  - Review approved → auto-creates integration + docs
Day 1, 17:05  - Integrator merges
Day 1, 17:30  - Documenter finishes
Day 1, 17:30  - Pipeline complete, feature shipped
```

Total time: ~8 hours of agent work, fully tracked and auditable.
