def tester_prompt(bead_id: str, base: str, stage: str) -> str:
    return _acceptance_prompt(bead_id, base)


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a verifier. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git fetch origin && git checkout origin/{base}
4. Run bead-specific tests — verify this bead's feature works post-merge
5. Run the FULL test suite — verify nothing is broken across the integrated codebase
   - Look for pytest.ini, pyproject.toml [tool.pytest], Makefile test targets, package.json scripts
   - Run all discovered tests, not just ones related to this bead
6. If full suite has no test infrastructure, note it in the comment and proceed with bead-specific verification only

If ALL PASS:
  bd update {bead_id} --status closed
  Exit

If ANY FAIL:
  bd comment {bead_id} "Acceptance failed: [details — specify whether bead-specific or integration failure]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
