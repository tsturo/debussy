def integrator_prompt(bead_id: str, base: str, stage: str) -> str:
    return f"""You are an autonomous integrator agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

Bead: {bead_id}
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git fetch origin && git checkout origin/{base}
4. git merge origin/feature/{bead_id} --no-ff
5. Resolve conflicts if any
6. Run tests after merge — if tests fail, abort: git merge --abort
7. git push origin HEAD:{base}
8. bd update {bead_id} --status closed
9. Exit

IMPORTANT: You are on a detached HEAD at origin/{base}. Merge origin/feature/{bead_id} and push with `git push origin HEAD:{base}`. NEVER merge into master.
After a successful merge, set status to CLOSED — acceptance testing happens in a separate batch step.

IF TESTS FAIL (before or after merge):
  bd comment {bead_id} "Tests failed: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

IF MERGE CONFLICTS cannot be resolved:
  bd comment {bead_id} "Merge conflict: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

START NOW. Do not wait for instructions. Begin with step 1."""
