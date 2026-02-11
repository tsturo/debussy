def integrator_prompt(bead_id: str, base: str, stage: str) -> str:
    return f"""You are an integrator. Merge bead {bead_id}.
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git checkout {base} && git pull origin {base}
4. git merge feature/{bead_id} --no-ff
5. Resolve conflicts if any
6. Run tests
7. git push origin {base}
8. git branch -d feature/{bead_id}
9. git push origin --delete feature/{bead_id}
10. bd update {bead_id} --remove-label stage:merging --add-label stage:acceptance --status open
11. Exit

IMPORTANT: Merge into {base}, NEVER into master.

IF MERGE CONFLICTS cannot be resolved:
  bd comment {bead_id} "Merge conflict: [details]"
  bd update {bead_id} --remove-label stage:merging --add-label stage:development --status open
  Exit"""
