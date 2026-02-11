def investigator_prompt(bead_id: str, base: str, stage: str) -> str:
    if stage == "stage:consolidating":
        return _consolidating_prompt(bead_id)
    return _investigating_prompt(bead_id)


def _investigating_prompt(bead_id: str) -> str:
    return f"""You are an investigator. Research bead {bead_id}.

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. Research the codebase, understand the problem
4. Document findings as bead comments: bd comment {bead_id} "Finding: [details]"
5. bd update {bead_id} --remove-label stage:investigating --status closed
6. Exit

IMPORTANT: Do NOT create developer tasks. Only document findings as comments.
A consolidation step will review all findings and create dev tasks.

IF BLOCKED or need more info:
  bd comment {bead_id} "Blocked: [reason]"
  bd update {bead_id} --remove-label stage:investigating --status open
  Exit"""


def _consolidating_prompt(bead_id: str) -> str:
    return f"""You are an investigator consolidating investigation findings for bead {bead_id}.

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. Read the bead's dependencies to find the investigation beads
4. For each investigation bead: bd show <investigation-bead-id> — read all findings from comments
5. Synthesize findings into a coherent plan
6. Write findings to .debussy/investigations/{bead_id}.md
7. bd comment {bead_id} "Investigation complete — see .debussy/investigations/{bead_id}.md"
8. bd update {bead_id} --remove-label stage:consolidating --status closed
9. Exit

The .md file should contain:
- Summary of findings
- Recommended approach
- Suggested task breakdown (conductor will create the actual beads)

Do NOT create beads — the conductor will read your .md file and create tasks.

IF BLOCKED or findings are insufficient:
  bd comment {bead_id} "Blocked: [reason]"
  bd update {bead_id} --remove-label stage:consolidating --status open
  Exit"""
