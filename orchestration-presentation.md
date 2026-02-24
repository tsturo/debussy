# Orchestrating AI Agents: From Chaos to Pipeline

## Presentation Outline

---

### 1. The Problem: Why Single-Agent Isn't Enough

- A single Claude Code agent can do a lot — but it hits walls on real projects
- Context window limits: one agent can't hold an entire codebase + task history + review feedback
- Sequential bottleneck: coding, reviewing, testing, merging — all waiting on one thread
- No separation of concerns: the same agent writes code and reviews it (fox guarding the henhouse)
- Error compounding: one bad decision cascades without checkpoints
- **Key question for the audience:** "How many of you have had an agent go off the rails 200 lines into a change?"

---

### 2. What Is Agent Orchestration?

- Coordinating multiple specialized agents working toward a shared goal
- Not just "run 5 agents in parallel" — that's parallelism, not orchestration
- Orchestration means: task decomposition, dependency management, state transitions, and quality gates
- Analogy: a film production — director doesn't operate the camera, edit footage, AND act. Each role is specialized, and a production pipeline coordinates them

---

### 3. Two Approaches to Orchestration

#### 3.1 Fire-and-Forget ("Launch and Pray")

- You decompose work into tasks, assign them to agents, and hope they figure it out
- Agents are expected to self-organize, communicate, and resolve conflicts on their own
- The orchestrator's job ends at task creation — it doesn't supervise execution
- Works when tasks are truly independent and well-specified
- Breaks down when: tasks have hidden dependencies, agents make conflicting assumptions, or quality drifts without anyone noticing
- Analogy: giving a group of freelancers separate briefs and hoping the pieces fit together at the end

#### 3.2 Active Conducting ("Hands on the Wheel")

- The conductor stays involved throughout — monitoring progress, reacting to signals, adjusting course
- Tasks are released incrementally, not all at once
- The conductor can re-prioritize, create follow-up tasks, or block work based on what's happening
- Tighter feedback loop: problems are caught mid-flight, not at integration time
- Analogy: an actual orchestra conductor — they don't play instruments, but they're shaping the performance in real time
- **Debussy takes this approach**: the watcher continuously polls state and routes work; the conductor (agent) monitors progress and intervenes

#### 3.3 The Tradeoff

- Fire-and-forget is simpler and scales easily — but fragile when tasks interact
- Active conducting has overhead — but catches integration problems early
- The right choice depends on task coupling: loosely coupled work tolerates fire-and-forget; tightly coupled work needs active supervision

---

### 4. Communication Models: How Agents Coordinate

#### 4.1 Agent-to-Agent Communication (Peer-to-Peer)

- Agents talk directly to each other — passing messages, sharing context, negotiating decisions
- Feels natural: mimics how human teams collaborate
- Problems in practice:
  - Conversations are lossy — agents forget, misinterpret, or hallucinate context from earlier messages
  - Coordination overhead grows quadratically: 5 agents = 10 possible conversation pairs
  - Hard to audit: "why did the system do X?" requires reading through agent chat logs
  - Doesn't survive restarts — conversation state is ephemeral
  - Agents can convince each other of wrong things (echo chamber effect)
- Best suited for: exploratory tasks, brainstorming, situations where the solution isn't well-defined

#### 4.2 Atomic Tasks + Central Coordinator (Hub-and-Spoke)

- Agents never talk to each other — they only interact with the task system
- Tasks are designed to be self-contained: everything an agent needs is in the task description
- The coordinator (watcher + conductor) is the only entity that sees the full picture
- Communication happens through state changes: status flags and labels, not conversations
- Advantages:
  - Dead simple to debug: look at the task state, not a chat transcript
  - Survives restarts: task state is persisted, agents are stateless
  - No coordination overhead between agents — each one focuses on its own work
  - Quality gates are structural, not conversational
- Tradeoff: requires better task decomposition upfront — if a task isn't self-contained, the agent gets stuck
- **Debussy uses this model**: agents signal through bead status, the watcher routes, agents never see each other

#### 4.3 The Connection Between Orchestration Style and Communication

- Fire-and-forget orchestration tends to need agent-to-agent communication — because no one is supervising, agents must self-coordinate
- Active conducting enables atomic tasks — because the conductor handles cross-task coordination, individual agents don't need to talk
- This is the key insight: **the more active your orchestrator, the less agents need to communicate with each other**
- Debussy combines active conducting + atomic tasks + signal-based communication — this is what makes the pipeline predictable and auditable

---

### 5. Core Concepts

#### 3.1 Separation of Roles

- Each agent has a single responsibility and a constrained toolset
- Roles in debussy: conductor, developer, reviewer, integrator, security-reviewer, tester, investigator
- Why this matters: a reviewer that can't write code can only approve or reject — it can't "just fix it," which forces proper feedback loops

#### 3.2 Pipeline as a State Machine

- Every task moves through defined stages: development → reviewing → merging → closed
- Transitions are owned by the system (watcher), not by agents
- Agents signal outcomes (success, rejected, blocked) — the orchestrator decides what happens next
- This prevents agents from skipping steps or self-promoting their own work

#### 3.3 The Watcher Pattern

- A central loop that polls task state and spawns agents based on stage labels
- Agents are stateless workers — they pick up a task, do their job, signal the result
- The watcher interprets signals and advances the pipeline
- Similar to a Kubernetes controller reconciliation loop

#### 3.4 Git Worktrees: Enabling True Parallelism

**The problem:**

- Git only has one working directory. If agent A is editing `UserService.java` on branch `feature/bd-001` and agent B needs to work on `PaymentService.java` on branch `feature/bd-002`, they can't — `git checkout` switches the entire repo, blowing away A's uncommitted work
- Without isolation, parallel agents step on each other: uncommitted changes from one agent leak into another's build, tests run against a mixed state, and merge conflicts appear in files nobody intentionally touched
- This is the #1 reason naive "just run multiple agents" approaches break down — the filesystem is a shared mutable resource

**The solution: git worktrees**

- `git worktree add ../feature-bd-001 feature/bd-001` creates a separate directory with its own checkout of that branch — same repo, shared `.git`, independent filesystem
- Each developer agent gets its own worktree: it can edit, build, test, and commit without any awareness of other agents working in parallel
- The shared `.git` means commits, branches, and history are visible across all worktrees — integrator can merge from any of them

**Why this matters for orchestration:**

- Worktrees turn a sequential constraint (one checkout at a time) into a parallel-ready setup
- No file locking needed — each agent operates in its own directory
- Agents are truly isolated: one agent's broken build doesn't affect another's test run
- Cleanup is simple: `git worktree remove` deletes the directory when the bead is done
- In the Camunda migration, this is what allowed 163 beads to be worked on by multiple developer agents simultaneously

**Without worktrees**, you'd need either: separate full clones of the repo (wasteful — duplicates the entire history), or sequential execution (one agent at a time — defeats the purpose of orchestration)

#### 3.5 Task Decomposition & Dependencies

- Conductor breaks work into small, independently deliverable beads (tasks)
- Dependencies (`--deps`) enforce ordering where needed
- Parallelism happens naturally: independent tasks run simultaneously, dependent tasks wait

#### 3.5 Quality Gates

- Code review is mandatory — every bead passes through a reviewer before merge
- Security-sensitive beads get an additional OWASP-aligned security review
- Batch acceptance testing runs after all beads in a feature are merged
- Rejection loops: failed review sends work back to development, not to a "fix-it" agent

#### 3.6 Investigation Pipeline: Research Before You Code

- Problem: agents that jump straight into coding often go in blind — they make wrong assumptions about the codebase, miss existing patterns, and produce work that needs heavy rework
- Solution: a dedicated investigation phase that runs before any development begins

**How it works:**

- Conductor creates multiple investigation beads scoped to different areas (e.g., "Investigate DMN migration", "Investigate Spring Boot config", "Investigate test patterns")
- Investigators run in parallel — each one researches its area, reads code, checks docs, and posts findings as bead comments
- A consolidation bead (with `--deps` on all investigation beads) waits for all investigators to finish, then a consolidation agent synthesizes all findings into a single .md document
- The conductor reads the consolidated findings and uses them to create well-informed development tasks

```
Investigate area A ──┐
Investigate area B ──┼──→ Consolidate findings ──→ .md file ──→ Conductor creates dev tasks
Investigate area C ──┘
```

**Why this matters:**

- Parallelism: 8 investigators can research 8 areas simultaneously — the investigation phase takes as long as the slowest one, not the sum
- Better task specs: development beads created after investigation have richer context — the developer knows what patterns to follow, what pitfalls to avoid, what APIs to use
- Early problem detection: in the Camunda migration, 86 findings surfaced before a single line of code was written. Issues like "Zeebe doesn't support escalation events" or "DMN typeRef changed from integer to number" were caught in research, not in debugging
- Prevents wasted work: without investigation, developers discover blockers mid-implementation and have to throw away code

**When to use it:**

- Migrating to unfamiliar technology (you don't know what you don't know)
- Large codebases where no single agent can hold enough context
- Tasks where the approach isn't obvious and multiple strategies exist
- When the cost of a wrong start is high (complex refactors, infrastructure changes)

**When to skip it:**

- Well-understood, routine tasks where the approach is clear
- Small changes where the developer can investigate inline
- When speed matters more than thoroughness (quick fixes, hotfixes)

---

### 6. Architecture: How Debussy Works

#### 4.1 The Pipeline

```
open → stage:development → stage:reviewing → [stage:security-review] → stage:merging → closed
```

- Optional security review for beads with the `security` label
- Investigation pipeline for research tasks (parallel investigation → consolidation)

#### 4.2 Agent Roles (detail)

| Role | Does | Doesn't |
|------|------|---------|
| Conductor | Decomposes work, creates tasks, monitors progress | Write code |
| Developer | Implements features, writes tests | Review own code, merge |
| Reviewer | Reviews code quality, runs tests | Write code, merge |
| Security Reviewer | OWASP-aligned security audit | Write code |
| Integrator | Merges branches, resolves simple conflicts | Make code changes |
| Tester | Runs acceptance tests on merged feature | Fix failures |
| Investigator | Researches codebase, documents findings | Create dev tasks |

#### 4.3 Branching Model

```
master (human-only merge)
  └── feature/<name>          ← conductor's branch
        ├── feature/bd-001    ← developer branches
        ├── feature/bd-002
        └── feature/bd-003
```

- Each developer works in an isolated git worktree
- Integrator merges sub-branches into the feature branch
- Human merges feature branch to master — agents never touch master

#### 4.4 Signal-Based Communication

- Agents don't talk to each other directly
- They communicate through task status: `in_progress`, `open`, `closed`, `blocked`
- Labels carry metadata: `rejected`, `security`, stage labels
- The watcher reads these signals and routes work accordingly

---

### 7. Comparison: Debussy vs. "Agent Teams"

| Aspect | Agent Teams (typical) | Debussy Pipeline |
|--------|----------------------|------------------|
| Coordination | Agents chat with each other | State machine + watcher |
| Role enforcement | Honor system / prompt-based | Structural — agents lack tools to violate roles |
| Error handling | Agent decides what to do | Watcher routes to correct stage |
| Parallelism | Ad-hoc | Dependency-resolved, capped |
| Quality gates | Optional | Mandatory (review, security review, acceptance) |
| State management | In-memory / conversation | Persistent task database (beads) |
| Merge safety | Varies | Agents never touch master |
| Reproducibility | Low — depends on conversation flow | High — same pipeline every time |

#### Why not just let agents talk to each other?

- Agent-to-agent communication is lossy and unpredictable
- Conversation-based coordination doesn't survive restarts
- Hard to audit: "why did the agent merge without review?" — no clear answer
- Pipeline approach: every transition is logged, every gate is explicit

---

### 8. Case Study: Camunda 7→8 Migration with Debussy

#### The Task

- Migrate a production microservice (`vf-onboard-bpm`) from Camunda 7 to Camunda 8 (Zeebe 8.8)
- Scope: 13 BPMN processes, 15 DMN decision tables, 37+ job workers, 321 unit tests

#### By the Numbers

| Metric | Value |
|--------|-------|
| Total beads (tasks) | 163 |
| Closed successfully | 162 |
| Rejections (reviewer caught real issues) | 6 |
| Unique agents spawned | 307 |
| Pipeline events | 19,032 |

#### What Worked

- **Investigation-first**: 8 parallel investigations (Spring Boot, DMN, BPMN, Delegates, Tests, Infrastructure, REST API, Database) before writing any code — produced 86 findings that predicted nearly every implementation issue
- **Granular task decomposition**: one bead per delegate, per DMN file, per test group — enabled true parallelism
- **Reviewer agents caught real bugs**: typeRef changes breaking downstream Java casts, resource leaks, overly invasive test patterns
- **Testing strategy challenge**: reviewer challenged the plan to migrate all 44 BPMN flow tests; decision to replace with 3-5 strategic E2E tests saved ~70 hours

#### What Didn't Work

- **Spawn storms**: some beads had 3000+ spawn attempts — agents repeatedly failing and retrying on the same task (merge conflicts from parallel edits, unresolved dependencies, tasks too tightly coupled)
- **Investigation blind spots**: 2 out of 8 investigations produced 0 findings — scope was wrong or agents lacked context. Should have been flagged and re-scoped earlier
- **Infrastructure wasn't investigated**: docker-compose issues were all discovered at runtime, not during the investigation phase — 7 infrastructure issues that could have been a pre-flight checklist
- **No circuit breaker**: a bead burning 3000 spawns wastes resources. Need automatic escalation after N failures

---

### 9. Lessons Learned

#### From the Design

- **Constraint is a feature**: agents do better work when their scope is narrow
- **Don't let agents self-evaluate**: separation of developer and reviewer catches real bugs
- **Rejection loops matter**: the ability to send work back to development is the most important quality mechanism
- **Human stays in the loop**: conductor sets direction, human merges to master — agents execute within guardrails
- **Stateless agents, stateful pipeline**: agents can crash, restart, or be replaced — the pipeline state survives

#### From the Migration (real-world use)

- **Investigation before implementation pays off massively**: 86 findings from parallel research meant developers rarely hit surprises. The few surprises (infrastructure) were exactly the area that wasn't investigated
- **Granularity enables parallelism, but creates merge pressure**: 163 beads = great parallelism, but parallel agents editing overlapping files caused merge conflicts and spawn storms
- **Reviewers are the unsung hero**: the 6 rejections weren't pedantic — they caught typeRef bugs, resource leaks, and a testing strategy that would have wasted 70 hours
- **Need failure budgets, not infinite retries**: without spawn limits, a stuck bead burns thousands of cycles. Circuit breakers and automatic escalation to the conductor are essential
- **Some tasks resist decomposition**: infrastructure setup (docker-compose) is inherently sequential and environment-dependent. Not everything fits the "atomic bead" model — recognize these early and handle them differently
- **0-finding investigations are a signal, not a success**: if an investigation produces nothing, it probably means the scope was wrong or the agent couldn't access what it needed. Treat silence as a red flag

---

### 10. When Do You Need Orchestration?

- You don't always need it — single agent is fine for small, well-defined tasks
- Consider orchestration when:
  - Multiple files/components need coordinated changes
  - You want code review as part of the automated workflow
  - Security review is required
  - You need reproducible, auditable development processes
  - Tasks have dependencies and need to run in a specific order
  - You want to parallelize work across independent tasks

---

### 11. Open Questions / Discussion

- **Granularity sweet spot**: 163 beads worked for this migration, but spawn storms suggest some tasks were too fine-grained or too coupled. Where's the line?
- **Investigation coverage**: how do you know your investigation plan covers the right areas? 2 out of 8 produced nothing — how to detect and re-scope early?
- **Failure budgets**: what's the right spawn limit before escalation? Too low = premature escalation; too high = wasted cycles (3000 spawns on one bead is clearly too many)
- **Infrastructure as a special case**: sequential, environment-dependent tasks don't fit the atomic-bead model well. Should there be a separate "Phase 0" pipeline for infra?
- **Cross-bead merge conflicts**: parallel agents editing overlapping files is the #1 cause of spawn storms. Can smarter task decomposition prevent this, or do we need file-level locking?
- **Agent observability**: 19,000 pipeline events but no easy way to see WHY a spawn failed without reading individual logs. What telemetry would make debugging faster?
- **Scaling to more services**: this was one microservice. What changes when you run 5 migrations in parallel? 10?
