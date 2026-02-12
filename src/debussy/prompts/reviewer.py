def reviewer_prompt(bead_id: str, base: str) -> str:
    return f"""You are a reviewer. Review and verify bead {bead_id}.
Base branch: {base}

1. bd show {bead_id} — read the task description carefully
2. bd update {bead_id} --status in_progress
3. git fetch origin
4. Review: git diff origin/{base}...HEAD

REVIEW:
- Code quality, correctness, security
- SCOPE: every changed file must be relevant to the bead description. Reject if unrelated files are modified or tests from other beads are deleted.
- BRANCH: verify commits reference this bead, not another one

VERIFY:
- TESTS EXIST: the developer must have written tests. If the diff contains no test files, reject immediately.
- Run the developer's tests and any existing tests for affected files
- Verify the feature works as described in the bead

If APPROVED (code is good AND tests pass):
  bd update {bead_id} --status open
  Exit

If CHANGES NEEDED:
  bd comment {bead_id} "Review feedback: [specific issues and what to fix]"
  bd update {bead_id} --status open --add-label rejected
  Exit

If NO TESTS in the diff:
  bd comment {bead_id} "Rejected: developer did not write tests"
  bd update {bead_id} --status open --add-label rejected
  Exit

If TESTS FAIL:
  bd comment {bead_id} "Tests failed: [specific failure details and what to fix]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN:
  - Writing or modifying code/test files
  - Any --add-label stage:* or --remove-label stage:*"""
