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
4. Review the changes (git diff {base}...HEAD)
5. Write automated tests for the new functionality
6. Run all tests
7. Commit and push the tests

If ALL TESTS PASS:
  bd update {bead_id} --remove-label stage:testing --add-label stage:merging --status open
  Exit

If TESTS FAIL:
  bd comment {bead_id} "Tests failed: [details]"
  bd update {bead_id} --remove-label stage:testing --add-label stage:development --status open
  Exit

IMPORTANT: Always write tests before approving. No untested code passes."""


def _acceptance_prompt(bead_id: str, base: str) -> str:
    return f"""You are a tester. Acceptance test for bead {bead_id} (post-merge).
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git checkout {base} && git pull origin {base}
4. Run full test suite, verify feature works

If PASS:
  bd update {bead_id} --remove-label stage:acceptance --status closed
  Exit

If FAIL:
  bd comment {bead_id} "Acceptance failed: [details]"
  bd update {bead_id} --remove-label stage:acceptance --add-label stage:development --status open
  Exit"""
