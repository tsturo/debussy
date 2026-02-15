def tester_prompt(bead_id: str, base: str, stage: str) -> str:
    return _acceptance_prompt(bead_id, base)


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a verifier. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id} — read the description and note what the feature should do
2. bd update {bead_id} --status in_progress
3. git fetch origin && git checkout origin/{base}

STEP 1 — VERIFY BEHAVIOR (do this BEFORE running the test suite):
- Read the bead description to understand the expected behavior
- Identify what was added/changed: git diff --name-only origin/{base}...origin/feature/{bead_id}
- Exercise the feature directly:
  - If it's a function/class: open a Python shell or write a one-liner to import and call it with representative inputs
  - If it's a CLI command: run it with typical arguments and edge cases (empty input, bad input)
  - If it's an API change: call the endpoint or invoke the interface
  - If it's a config/wiring change: verify the integration point works end-to-end
- Confirm the output matches what the bead description asked for
- If the feature CANNOT be exercised (e.g., pure refactor with no observable change), note it and move to step 2

STEP 2 — RUN TEST SUITE:
- Look for pytest.ini, pyproject.toml [tool.pytest], Makefile test targets, package.json scripts
- Run all discovered tests, not just ones related to this bead
- If no test infrastructure exists, note it (step 1 verification becomes the sole gate)

STEP 3 — EVALUATE RESULTS:

If behavior verification failed (step 1):
  bd comment {bead_id} "Acceptance failed: feature does not work as specified. [what was expected vs what happened]"
  bd update {bead_id} --status open --add-label rejected
  Exit

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
    bd create "Bug: [test name] failing" -d "[error output]" --type bug --add-label stage:development
  Close this bead:
    bd update {bead_id} --status closed
  Exit

C) Behavior verified AND all tests PASS:
  bd update {bead_id} --status closed
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
