def tester_prompt(bead_id: str, base: str, stage: str) -> str:
    if stage == "stage:acceptance":
        return _acceptance_prompt(bead_id, base)
    return _testing_prompt(bead_id, base)


def _testing_prompt(bead_id: str, base: str) -> str:
    return f"""You are a tester. Test bead {bead_id}.
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git checkout feature/{bead_id}
4. Review the changes (git diff {base}...HEAD) — understand ONLY what changed
5. Write targeted tests for the diff — not the entire codebase
6. Run the relevant tests (not the full suite unless changes are broad)
7. Commit and push the tests

EFFICIENCY:
- Focus ONLY on testing what the developer changed
- If the developer already wrote tests, verify they're adequate and add missing cases
- Don't write tests for pre-existing code that wasn't modified
- Run targeted test files, not the entire suite

If ALL TESTS PASS:
  bd update {bead_id} --status open
  Exit

If TESTS FAIL:
  bd comment {bead_id} "Tests failed: [specific failure details and what to fix]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a tester. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git checkout {base} && git pull origin {base}
4. Run the test suite relevant to this bead's changes — verify feature works post-merge

If PASS:
  bd update {bead_id} --status closed
  Exit

If FAIL:
  bd comment {bead_id} "Acceptance failed: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
