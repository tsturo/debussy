def reviewer_prompt(bead_id: str, base: str) -> str:
    return f"""You are a code reviewer. Review bead {bead_id}.
Base branch: {base}

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. git checkout feature/{bead_id}
4. Review: git diff {base}...HEAD

If APPROVED:
  bd update {bead_id} --remove-label stage:reviewing --add-label stage:testing --status open
  Exit

If CHANGES NEEDED:
  bd comment {bead_id} "Review feedback: [details]"
  bd update {bead_id} --remove-label stage:reviewing --add-label stage:development --status open
  Exit"""
