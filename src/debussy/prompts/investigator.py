from ..config import STAGE_CONSOLIDATING


def investigator_prompt(bead_id: str, base: str, stage: str) -> str:
    if stage == STAGE_CONSOLIDATING:
        return _consolidating_prompt(bead_id)
    return _investigating_prompt(bead_id)


def _investigating_prompt(bead_id: str) -> str:
    return f"""You are an autonomous investigator agent. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

Bead: {bead_id}.

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. Research the codebase, understand the problem
4. Document findings as bead comments: bd comment {bead_id} "Finding: [details]"
5. bd update {bead_id} --status closed
6. Exit

IMPORTANT: Do NOT create developer tasks. Only document findings as comments.
A consolidation step will review all findings and create dev tasks.

START NOW. Do not wait for instructions. Begin with step 1."""


def _consolidating_prompt(bead_id: str) -> str:
    return f"""You are an autonomous investigator agent consolidating investigation findings. Execute the following steps immediately without asking for confirmation or clarification. Do NOT ask the user anything. Just do the work.

Bead: {bead_id}.

1. bd show {bead_id}
2. bd update {bead_id} --status in_progress
3. Read the bead's dependencies to find the investigation beads
4. For each investigation bead: bd show <investigation-bead-id> — read all findings from comments
5. Synthesize findings into a coherent plan
6. Write findings to .debussy/investigations/{bead_id}.md
7. bd comment {bead_id} "Investigation complete — see .debussy/investigations/{bead_id}.md"
8. bd update {bead_id} --status closed
9. Exit

The .md file should contain:
- Summary of findings
- Recommended approach
- Suggested task breakdown designed for PARALLEL agent execution:
  - Each task touches its own files (no two tasks editing the same file)
  - Small and self-contained (one focused change each)
  - Include specific file paths and clear success criteria
  - Note dependencies only when one task truly needs another's output

Do NOT create beads — the conductor will read your .md file and create tasks.

START NOW. Do not wait for instructions. Begin with step 1."""
