---
name: git-strategy
description: Git branching and commit conventions for the bead pipeline
---

## Commit Messages

```
[bd-xxx] Brief description
```

## Branch Model

```
master (manual merge only by user — NEVER merge to master)
  └── feature/<name>          ← conductor's base branch
        ├── feature/bd-001    ← developer branches
        ├── feature/bd-002
        └── feature/bd-003
```

- Developers work on `feature/<bead-id>` branches
- Integrator merges developer branches into the conductor's base branch
- NEVER merge to master — only the user does that manually
- Always add all changed files to git
