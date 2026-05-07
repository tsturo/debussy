# Roadmap: Skill Extraction & Refinements

**Date:** 2026-04-28
**Status:** Outline only — full specs will be written when each is ready to start.

This document captures design ideas deferred from the bundled spec discussion on 2026-04-28, after splitting the work into manageable specs. Spec 1 (`2026-04-28-pipeline-simplification-design.md`) is the only spec currently approved for implementation; it has since been narrowed to **just the integrator change** because most of the originally-planned pipeline simplification (drop skeptic, fold review perspectives, remove post-merge stages) was already done on origin in commit `c2c19a4` (2026-04-06). The two specs below are placeholders so we don't lose context.

## Spec 2: Skill Extraction (planned, not yet specced)

### Goal

Extract the reusable judgment/checklist content from debussy's agent prompts into Claude Code skills under the `dbs-` prefix. Skills become a single source of truth and can also be invoked manually in interactive Claude Code sessions.

### Skills to extract (subject to revision when Spec 2 is written)

After Spec 1 lands, the surviving roles are: `conductor`, `developer`, `reviewer`, `security-reviewer`, `arch-reviewer`, `integrator`, `tester`. That gives us up to 7 skills (`dbs-conductor`, `dbs-developer`, `dbs-code-review`, `dbs-security-review`, `dbs-arch-review`, `dbs-integrator`, `dbs-tester`), plus possibly `dbs-perf-review` and `dbs-ux-review` extracted from the reviewer's conditional sections.

### Open design questions (to resolve when writing Spec 2)

- **Skill output contract:** how do skills signal verdict (APPROVED / REJECTED / BLOCKED) back to the wrapper? Token-based contract risks model paraphrasing or fabrication; Python-side parsing of Skill tool return value would be more reliable but requires deeper integration.
- **Skill invocation reliability:** how do we ensure the spawned agent actually invokes the skill instead of improvising from training? Options: enforce via wrapper script, inject test expectations the model can't satisfy without invoking.
- **Voice and dual-purpose use:** skills should be usable in interactive sessions (soft voice) AND drive autonomous agents (firm voice). The wrapper is responsible for re-asserting autonomous framing around skill invocations.
- **Distribution:** skills authored in `<repo>/skills/dbs-<name>/SKILL.md`, installed into `~/.claude/skills/` via a `debussy install-skills` command (symlink-based). Preflight checks symlinks exist before spawning.
- **Multi-checkout collisions:** if the user has multiple debussy checkouts, the second `install-skills` silently steals symlinks from the first. Detection or warning needed.
- **Versioning policy:** always-latest (skills loaded fresh each invocation) keeps it simple but means in-flight pipelines can pick up mid-edit changes.
- **Reviewer with multiple skills:** if `dbs-code-review` + `dbs-perf-review` + `dbs-ux-review` all run, how do verdicts combine? Likely: code-review is dominant, advisory skills (perf, ux) only file follow-ups. But this changes the Spec 1 design where ux/perf can block — needs a deliberate decision.

## Spec 3: Tags & Distribution Refinements (planned, not yet specced)

### Goal

Once skills exist, harden the integration points that Spec 2 leaves rough.

### Open items

- **`tags.py` single source of truth:** a Python module exposing `KNOWN_TAGS` and a `tag_skill_map`. Both wrappers and conductor reference it. Drift detection between this module and the conductor skill body.
- **`takt show --json`:** structured tag delivery to spawned agents. Replaces parsing tags from the free-text user message. Requires defining the JSON schema explicitly (at minimum: `{labels: [...]}`).
- **Skill description audit:** the frontmatter `description` field drives Claude's auto-loading in interactive use. Need explicit guidance and a review pass that grades skills against it.
- **Two-pass expert review process for skills:** with explicit acceptance criteria for findings (actionable vs dismissable) and a termination rule (when does pass 3 trigger?).
- **Concurrent worktree edits:** what happens when a skill's source file is edited while a spawned agent in another worktree is reading it? Document or defend.

## Why split this way

The bundled spec attempted Spec 1 + Spec 2 + Spec 3 in one design. After two rounds of expert review, reviewers kept surfacing plausible new issues — not because the design was wrong, but because the surface area was too large for a single review pass to settle. Splitting lets each spec land on its own merits, and each round of review actually converges.
