# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer.*

Beads for memory. Native subagents for roles. Bash for automation.

---

## What You Get

```
debussy/
├── CLAUDE.md                    # Universal guidelines (Karpathy principles + multi-agent rules)
├── WORKFLOW.md                  # Complete operational guide
├── .claude/subagents/
│   ├── conductor.md           # The Conductor — orchestrates all agents
│   ├── developer.md             # Implements features, fixes bugs
│   ├── architect.md             # Plans technical approach, reviews structure, creates ADRs
│   ├── designer.md              # Plans UX, reviews accessibility
│   ├── tester.md                # Writes tests, runs coverage
│   ├── reviewer.md              # Code review, security audit
│   ├── documenter.md            # Documentation, READMEs
│   ├── integrator.md            # Merges code, resolves conflicts
│   └── devops.md                # CI/CD, infrastructure, deployment
├── scripts/
│   ├── start-agents.sh          # One-command tmux workspace
│   ├── handoff-watcher.sh       # Automated pipeline triggers
│   └── handoff.sh               # Manual handoff helper
└── config/
    └── pipelines.yaml           # Pipeline definitions
```

---

## Quick Start

### Prerequisites

- [Beads](https://github.com/steveyegge/beads) installed (`brew install beads`)
- [Claude Code](https://claude.ai/code) with Max plan (for parallel sessions)
- tmux (optional, for multi-window setup)

### Setup

```bash
# Clone
git clone https://github.com/anthropics/debussy.git
cd debussy

# Copy to your project
cp -r .claude CLAUDE.md WORKFLOW.md scripts config /path/to/your-project/
cd /path/to/your-project

# Initialize Beads
bd init
bd setup claude
```

### Run

**Start with the conductor:**
```bash
claude
# → "Run as @conductor. Here's my requirement: [your requirement]"
```

The conductor will:
1. Delegate planning to @architect (and @designer if UI-related)
2. Wait for beads to be created
3. Assign tasks to workers

**For parallel execution, add worker terminals:**
```bash
# Terminal 2+: Workers
claude --resume
# → "Run as @developer. Check bd ready for my assigned tasks."
```

Or use the full orchestra script:
```bash
./scripts/start-agents.sh
```

---

## The Principles

### 1. Think Before Coding
> Don't assume. Don't hide confusion. Surface tradeoffs.

**Multi-agent rule:** Ambiguity? File a Bead with `--status blocked`. Don't guess.

### 2. Simplicity First
> Minimum code that solves the problem. Nothing speculative.

**Multi-agent rule:** @architect may recommend refactors — but via Beads, not direct changes.

### 3. Surgical Changes
> Touch only what you must. Clean up only your own mess.

**Multi-agent rule:** Discovered work outside your scope? File a new Bead. Don't scope-creep.

### 4. Goal-Driven Execution
> Define success criteria. Loop until verified.

**Multi-agent rule:** Your Bead description IS your success criteria. If vague, ask first.

---

## The Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  USER → @CONDUCTOR                                              │
│                                                                 │
│   requirement ──▶ delegates to @architect + @designer           │
│                           │                                     │
│                           ▼                                     │
│                    beads created                                │
│                           │                                     │
│                           ▼                                     │
│              @conductor assigns from bd ready                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  EXECUTION                                                      │
│                                                                 │
│   feature ──▶ test ──▶ review ──▶ integration ──▶ done         │
│      │          │         │            │                        │
│      │          │         │            └──▶ docs (parallel)     │
│      │          │         │                                     │
│      │          │         └──▶ changes requested? → developer   │
│      │          │                                               │
│      │          └──▶ failed? → developer (bug fix)              │
│      │                                                          │
│      └──▶ @developer implements                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Handoffs are automatic.** Complete a task → next task is created and assigned.

| Completed | Creates | Assigns To |
|-----------|---------|------------|
| `feature` done | `test: [title]` | @tester |
| `test` passed | `review: [title]` | @reviewer |
| `test` failed | `bug: fix [title]` | @developer |
| `review` approved | `integration` + `docs` | @integrator, @documenter |
| P1 `bug` done | `hotfix` (fast-track) | @integrator |

---

## Agent Roles

| Role | Writes Code | Purpose |
|------|-------------|---------|
| **@conductor** | ❌ | Entry point. Receives requirements, delegates planning, assigns tasks, monitors progress |
| **@architect** | ❌ | Plans technical approach, breaks down requirements, reviews structure, creates ADRs |
| **@designer** | ❌ | Plans UX flows and states, defines accessibility requirements, reviews UI |
| **@developer** | ✅ | Implements features, fixes bugs |
| **@tester** | ✅ (tests) | Writes tests, runs coverage, reports results |
| **@reviewer** | ❌ | Code review, security audit, files issue Beads |
| **@documenter** | ✅ (docs) | READMEs, API docs, code comments |
| **@integrator** | ✅ | Merges branches, resolves conflicts, manages PRs |
| **@devops** | ✅ | CI/CD pipelines, Docker, Kubernetes, infrastructure |

---

## Credits

- **[Beads](https://github.com/steveyegge/beads)** by Steve Yegge — The memory layer

---

## License

MIT License. See [LICENSE](LICENSE).
