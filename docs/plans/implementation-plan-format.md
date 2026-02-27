# Implementation Plan Output Format

When investigating a new feature or application, produce a plan document that a Debussy conductor can directly translate into beads. The plan must respect the parallel agent execution model — multiple developers work simultaneously, each on one bead, with no coordination between them.

## Document Structure

The plan must follow this structure exactly:

```markdown
# [Feature Name] — Implementation Plan

## Goal
One paragraph. What are we building and why. Concrete end state, not aspirations.

## Architecture Decisions
Key technical choices made during investigation. Each decision should state:
- What was decided
- Why (brief rationale)
- What was rejected and why

## Phase Breakdown

### Phase 1: [Foundation / name]
Beads in a phase are released together and run in parallel.
A batch acceptance test runs after all beads in the phase merge.

#### Bead: "[title]"
- **Files**: exact paths to create or modify (1-2 max)
- **Description**: what the developer must do, specific enough to act on without context
- **Acceptance criteria**: observable, testable outcomes (not "it works")
- **Labels**: `security` | `frontend` | none
- **Depends on**: bead title from earlier phase, or none
- **Test criteria**: only if the task involves logic worth testing (skip for config, wiring, types)

#### Bead: "[title]"
...

### Phase 2: [Feature layer / name]
(depends on Phase 1 batch acceptance passing)

#### Bead: ...

### Phase 3: ...

## File Ownership Map
Table showing which file is touched by which bead.
Two beads MUST NOT touch the same file unless serialized with --deps.

| File | Bead |
|------|------|
| src/models/user.ts | Create User model |
| src/api/auth/login.ts | Add login endpoint |

## Risks & Open Questions
Anything the conductor should consider before releasing tasks.
```

## Rules for Bead Design

1. **One bead = one file or one component, one behavior.** If you'd describe it with "and", split it. If it needs 3+ files, split it.
2. **No file collisions within a phase.** Two beads in the same phase must not modify the same file. Use the file ownership map to verify.
3. **Name exact file paths.** Vague beads produce vague code. `src/models/user.ts` not "the user model".
4. **Acceptance criteria must be verifiable.** "Returns 200 with valid JWT" not "works correctly". The reviewer and tester will use these criteria literally.
5. **Mark security-sensitive beads.** Anything handling user input, auth, crypto, file paths, or DB queries with dynamic input gets the `security` label.
6. **Mark frontend beads.** Any UI/visual work gets the `frontend` label. Include the dev server command in the description.
7. **Dependencies only when truly needed.** If B reads a file that A creates, B depends on A. If they're independent modules, no dependency. Over-serialization kills parallelism.
8. **Phases gate on batch acceptance.** Phase 2 beads should not start until Phase 1's batch acceptance passes. Within a phase, everything runs in parallel.
9. **Include test criteria selectively.** New logic, validation, API endpoints, data transformations — yes. Config files, type definitions, wiring — no.

## What Makes a Bad Plan

- Beads described as "Implement X feature" with no file paths or acceptance criteria
- A single phase with 15 beads that have hidden ordering dependencies
- File collisions not caught (two beads edit the same file in the same phase)
- Acceptance criteria that require human judgment ("looks good", "feels responsive")
- Missing security/frontend labels on beads that clearly need them
- Phases that aren't meaningful groupings (just arbitrary splits)

## What Makes a Good Plan

- A conductor can create all beads by reading the plan linearly
- Each bead description is copy-pasteable into `bd create "title" -d "description"`
- The file ownership map has zero collisions within any phase
- A developer picking up any single bead can complete it without reading other beads
- Acceptance criteria map directly to assertions a test or reviewer can check
