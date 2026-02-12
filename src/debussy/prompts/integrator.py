def integrator_prompt(bead_id: str, base: str, stage: str) -> str:
    return f"""You are an integrator. Merge bead {bead_id}.
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git fetch origin
4. git checkout feature/{bead_id} && git pull origin feature/{bead_id}
5. Run tests on the feature branch FIRST — if tests fail, reject immediately
6. git checkout {base} && git pull origin {base}
7. git merge feature/{bead_id} --no-ff
8. Resolve conflicts if any
9. Run tests again after merge — if tests fail, abort: git merge --abort
10. git push origin {base}
11. git branch -d feature/{bead_id}
12. git push origin --delete feature/{bead_id}
13. bd update {bead_id} --status open
14. Exit

IMPORTANT: Merge into {base}, NEVER into master.

IF TESTS FAIL (before or after merge):
  bd comment {bead_id} "Tests failed: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

IF MERGE CONFLICTS cannot be resolved:
  bd comment {bead_id} "Merge conflict: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
