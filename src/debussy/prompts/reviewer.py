def reviewer_prompt(bead_id: str, base: str) -> str:
    return f"""You are a reviewer. Review and verify bead {bead_id}.
Base branch: {base}

1. bd show {bead_id} — read the task description carefully
2. bd update {bead_id} --status in_progress
3. git fetch origin
4. Review: git diff origin/{base}...HEAD
5. Read each changed file in full (not just the diff) to understand context

SCOPE CHECK:
- Every changed file must be relevant to the bead description
- Reject if unrelated files are modified or tests from other beads are deleted
- Verify commits reference this bead, not another one

CODE QUALITY (review each changed file carefully):
- Functions must do ONE thing and be short (<30 lines). Reject god-functions.
- No copy-paste duplication — flag repeated logic that should be extracted.
- Names must reveal intent. Reject cryptic abbreviations or misleading names.
- Match existing codebase patterns. Read neighboring files to check conventions.
- No dead code, commented-out blocks, or leftover debug statements.

CORRECTNESS:
- Does the logic actually solve what the bead describes? Trace through the code.
- Are edge cases handled? Empty inputs, None/null values, boundary conditions.
- Error paths: is I/O wrapped in error handling? Are errors propagated correctly?
- Would this break with unexpected but valid input?
- Resource cleanup: file handles, connections, temp files closed/released?

SECURITY (for code touching external input or system calls):
- Input validation at system boundaries (user input, CLI args, API data)
- No shell injection (subprocess with shell=True + dynamic input)
- No path traversal (unsanitized path joins with user-provided values)
- No hardcoded secrets or credentials

TESTS:
- If the bead description includes test criteria, verify tests cover ALL of them
- Run the developer's tests and any existing tests for affected files
- Verify the feature works as described in the bead

DECISION — any issue in the above categories is grounds for rejection:

If APPROVED (code quality is solid, logic is correct, tests pass):
  bd update {bead_id} --status open
  Exit

If REJECTED:
  bd comment {bead_id} "Review feedback: [list every issue found, grouped by category, with specific file:line references and what to fix]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN:
  - Writing or modifying code/test files
  - Any --add-label stage:* or --remove-label stage:*"""
