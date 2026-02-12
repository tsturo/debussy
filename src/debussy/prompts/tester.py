def tester_prompt(bead_id: str, base: str, stage: str) -> str:
    return _acceptance_prompt(bead_id, base)


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a verifier. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git fetch origin && git checkout origin/{base}
4. Run the test suite relevant to this bead's changes — verify feature works post-merge

If PASS:
  bd update {bead_id} --status closed
  Exit

If FAIL:
  bd comment {bead_id} "Acceptance failed: [details]"
  bd update {bead_id} --status open --add-label rejected
  Exit

FORBIDDEN: Any --add-label stage:* or --remove-label stage:*"""
