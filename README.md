# Debussy

**Multi-agent orchestration for Claude Code.**

*Named after Claude Debussy, the impressionist composer — because great work emerges when many voices play in harmony.*

> *"Music is the space between the notes."* — Claude Debussy

Beads for memory. Native subagents for roles. Bash for automation.  
No frameworks. No $100/hour burn rate. Just a sensible starting point.

---

## Why This Exists

Multi-agent Claude Code is powerful but the options are overwhelming:

| Tool | Problem |
|------|---------|
| **Gas Town** | Complex, chaotic, requires Stage 7+ experience, $100/hr burn |
| **Beads alone** | Great memory, but no roles, no handoffs, no coordination |
| **claude-flow** | Feature overload, steep learning curve |
| **Native subagents** | No state persistence, no pipeline automation |

**Debussy fills the gap** — a learnable, practical setup that teaches you multi-agent fundamentals before you graduate to heavier tools.

---

## What You Get

```
debussy/
├── CLAUDE.md                    # Universal guidelines (Karpathy principles + multi-agent rules)
├── WORKFLOW.md                  # Complete operational guide
├── .claude/subagents/
│   ├── coordinator.md           # The Conductor — orchestrates all agents
│   ├── developer.md             # Implements features, fixes bugs
│   ├── architect.md             # Reviews structure, creates ADRs
│   ├── designer.md              # UX/UI review, accessibility
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

### Setup (2 minutes)

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/debussy.git
cd debussy

# Copy to your project
cp -r .claude CLAUDE.md WORKFLOW.md scripts config /path/to/your-project/
cd /path/to/your-project

# Initialize Beads
bd init
bd setup claude

# Create your first task
bd create "Implement user authentication" -t feature -p 1
```

### Run

**Option A: Full orchestra**
```bash
./scripts/start-agents.sh
```
This opens a tmux workspace with all agents ready.

**Option B: Manual ensemble**
```bash
# Terminal 1: Start handoff watcher
./scripts/handoff-watcher.sh watch

# Terminal 2: Conductor
claude
# → "Run as @coordinator. Check bd ready and assign tasks."

# Terminal 3+: Musicians
claude --resume
# → "Run as @developer. Check bd ready for my assigned tasks."
```

---

## The Principles

Based on [Andrej Karpathy's observations](https://github.com/forrestchang/andrej-karpathy-skills) about LLM coding pitfalls, adapted for multi-agent workflows:

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

Work flows automatically through stages:

```
┌─────────────────────────────────────────────────────────────────┐
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
| **@coordinator** | ❌ | Assigns work, monitors progress, handles escalations |
| **@developer** | ✅ | Implements features, fixes bugs |
| **@architect** | ❌ | Reviews structure, files refactor Beads, creates ADRs |
| **@designer** | ❌ | UX/UI review, accessibility audit, design consistency |
| **@tester** | ✅ (tests) | Writes tests, runs coverage, reports results |
| **@reviewer** | ❌ | Code review, security audit, files issue Beads |
| **@documenter** | ✅ (docs) | READMEs, API docs, code comments |
| **@integrator** | ✅ | Merges branches, resolves conflicts, manages PRs |
| **@devops** | ✅ | CI/CD pipelines, Docker, Kubernetes, infrastructure |

---

## When to Use This

### ✅ Use Debussy if you:
- Want to learn multi-agent orchestration fundamentals
- Have a Claude Max plan and want to use parallel sessions productively
- Prefer understanding your tools over black-box frameworks
- Want something working in 10 minutes, not 10 hours

### ❌ Use something else if you:
- Need 20-30 agents running simultaneously → [Gas Town](https://github.com/steveyegge/gastown)
- Want managed infrastructure and learning loops → [claude-flow](https://github.com/ruvnet/claude-flow)
- Just need memory without roles → [Beads](https://github.com/steveyegge/beads) alone
- Don't have Claude Max → Single-agent workflow is fine

---

## Comparison

| Feature | Debussy | Gas Town | claude-flow | Beads Only |
|---------|---------|----------|-------------|------------|
| Setup time | 2 min | 30+ min | 15 min | 1 min |
| Learning curve | Low | High | Medium | Low |
| Parallel agents | 5-10 | 20-30 | 10+ | Manual |
| Automated handoffs | ✅ | ✅ | ✅ | ❌ |
| Cost control | ✅ | ❌ | ✅ | ✅ |
| State persistence | Beads | Beads | Built-in | Beads |
| Pre-defined roles | 9 | 7 | 60+ | 0 |
| Dependencies | Beads, bash | Beads, Go, tmux | Node.js | Go |

---

## Roadmap

- [ ] Example project with sample workflow
- [ ] Slack/Discord notifications for handoffs
- [ ] Cost tracking per agent
- [ ] Conflict detection (warn when agents touch same files)
- [ ] Web dashboard for pipeline status
- [ ] Integration with GitHub Issues (two-way sync)

---

## Contributing

Contributions welcome! This project is intentionally simple — please keep it that way.

**Good contributions:**
- Bug fixes in handoff scripts
- Documentation improvements
- New agent roles (if genuinely useful)
- Better error handling

**Please discuss first:**
- Major architectural changes
- New dependencies
- Framework integrations

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Credits

- **[Beads](https://github.com/steveyegge/beads)** by Steve Yegge — The memory layer that makes this possible
- **[Karpathy Guidelines](https://github.com/forrestchang/andrej-karpathy-skills)** by forrestchang — Principles adapted from Andrej Karpathy's observations
- **[Gas Town](https://github.com/steveyegge/gastown)** — Inspiration for coordinator/worker architecture

---

## License

MIT License. See [LICENSE](LICENSE).

---

*Because the best orchestras don't need chaos to make music.*
