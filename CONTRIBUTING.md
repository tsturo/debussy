# Contributing to Claude Crew

Thank you for your interest in contributing! This project aims to make multi-agent Claude Code workflows accessible to everyone.

## Ways to Contribute

### 1. Report Issues

Found a bug or have a suggestion? [Open an issue](https://github.com/tomek-grzesiak/claude-crew/issues) with:

- **Bug reports:** Steps to reproduce, expected vs actual behavior, your environment
- **Feature requests:** Use case, proposed solution, alternatives considered

### 2. Improve Documentation

Documentation improvements are always welcome:

- Fix typos, clarify confusing sections
- Add examples from your own usage
- Translate to other languages
- Create video tutorials

### 3. Submit Code

#### Setup

```bash
git clone https://github.com/tomek-grzesiak/claude-crew.git
cd claude-crew
```

#### Making Changes

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Test with a real project
4. Commit with clear messages: `git commit -m "Add: description of change"`
5. Push: `git push origin feature/your-feature`
6. Open a Pull Request

#### Code Guidelines

- **Scripts:** Keep bash scripts POSIX-compatible where possible
- **Subagents:** Follow the existing `.md` format with YAML frontmatter
- **CLAUDE.md:** Keep it concise — agents read this every session
- **Comments:** Explain *why*, not *what*

### 4. Share Your Experience

- Write a blog post about using Claude Crew
- Share on Twitter/X, LinkedIn, or your preferred platform
- Present at meetups or conferences
- Create example projects

## Areas Where Help is Needed

### High Priority

- [ ] **Windows compatibility** — Port bash scripts to work on Windows (PowerShell or WSL guidance)
- [ ] **Testing on different stacks** — Validate workflows with Python, Java, Go, Rust projects
- [ ] **Conflict detection** — Warn when multiple agents are about to touch the same files

### Medium Priority

- [ ] **Notifications** — Slack/Discord webhooks for handoff events
- [ ] **Cost tracking** — Track token usage per agent session
- [ ] **GitHub Issues sync** — Two-way sync between Beads and GitHub Issues

### Nice to Have

- [ ] **Web dashboard** — Visualize pipeline status
- [ ] **VS Code extension** — Show Beads status in editor
- [ ] **Example projects** — Complete sample repos showing the workflow

## Pull Request Guidelines

### Before Submitting

- [ ] Test your changes with a real project
- [ ] Update documentation if needed
- [ ] Keep changes focused — one feature/fix per PR

### PR Description

Include:
- What the change does
- Why it's needed
- How you tested it
- Screenshots/logs if applicable

### Review Process

1. Maintainer reviews within a few days
2. Address any feedback
3. Once approved, maintainer merges

## Code of Conduct

- Be respectful and constructive
- Assume good intent
- Help others learn
- Credit others' work

## Questions?

- Open a [Discussion](https://github.com/tomek-grzesiak/claude-crew/discussions) for general questions
- Tag `@tomek-grzesiak` in issues if you need direct input

---

Thanks for helping make multi-agent Claude Code accessible to everyone! 🚀
