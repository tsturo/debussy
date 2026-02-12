def tester_prompt(bead_id: str, base: str, stage: str) -> str:
    return _acceptance_prompt(bead_id, base)


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a verifier. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git fetch origin && git checkout origin/{base}
4. Run bead-specific tests — verify this bead's feature works post-merge
5. Run the FULL test suite to catch regressions
   - Look for pytest.ini, pyproject.toml [tool.pytest], Makefile test targets, package.json scripts
   - Run all discovered tests, not just ones related to this bead
6. If no test infrastructure exists, note it and proceed with bead-specific verification only

RESULTS:

If tests fail, check quickly: does the failing test touch files changed by this bead?
  git diff --name-only origin/{base}...origin/feature/{bead_id}
Compare with the failing test's imports/files. Keep it simple — no deep forensics.

A) Failure caused by this bead (test covers files this bead changed):
  bd comment {bead_id} "Acceptance failed: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

B) Failure NOT caused by this bead (test covers unrelated code):
  For each unrelated failure, check if a bug already exists:
    bd search "[test name]" --type bug --status open
  If no existing bug found, create one:
    bd create "Bug: [test name] failing" -d "[error output]" --type bug
  Close this bead:
    bd update {bead_id} --status closed
  Exit

C) All tests PASS:
  bd update {bead_id} --status closed
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
