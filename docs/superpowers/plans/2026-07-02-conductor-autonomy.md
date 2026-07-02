# Conductor Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bake the monitor-and-fix supervision loop into the conductor prompt, add an `autonomy` config mode (auto/manual), and refresh per-role model defaults with per-role effort.

**Architecture:** Three independent seams: (1) `prompts/conductor.md` gains a PIPELINE SUPERVISION section with an `AUTONOMY_INSTRUCTIONS` placeholder substituted in `prompts/__init__.py` (same pattern as `MONITOR_INTERVAL`); (2) `config.py` gains `autonomy` and `role_efforts` defaults plus a `role_cli_args()` helper; (3) `spawner.py` and `tmux.py` use the helper to pass `--model`/`--effort`.

**Tech Stack:** Python 3, pytest (some modules use unittest style — match the file you edit), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-02-conductor-autonomy-design.md`

## Global Constraints

- No code comments (user rule).
- Plain model IDs, no `[1m]` suffix: `claude-fable-5`, `claude-sonnet-5`, `claude-opus-4-8`.
- The shared helper lives in `config.py`, NOT `agent.py` — `agent.py` imports from `tmux.py`, so `tmux.py` importing from `agent.py` would be circular.
- Run tests with: `python -m pytest tests/ -q` (individual: `python -m pytest tests/test_config.py -q`).
- Commit messages: plain imperative description (this is meta-work on debussy itself, not a pipeline task, so no `[PRJ-N]` prefix).

---

### Task 1: Config defaults — `autonomy`, `role_efforts`, refreshed `role_models`

**Files:**
- Modify: `src/debussy/config.py:46-67` (DEFAULTS), `src/debussy/config.py:156-161` (KNOWN_KEYS)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `get_config()["autonomy"]` → `"auto"`; `get_config()["role_efforts"]` → dict role→level; `get_config()["role_models"]` → dict role→current model IDs. Consumed by Tasks 2 and 5.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_config.py`:

```python
def test_autonomy_defaults_to_auto(project_dir):
    assert get_config()["autonomy"] == "auto"


def test_role_models_default_to_current_generation(project_dir):
    assert get_config()["role_models"] == {
        "conductor": "claude-fable-5",
        "developer": "claude-sonnet-5",
        "reviewer": "claude-opus-4-8",
        "security-reviewer": "claude-fable-5",
        "integrator": "claude-sonnet-5",
        "tester": "claude-sonnet-5",
    }


def test_role_efforts_cover_same_roles_as_role_models(project_dir):
    cfg = get_config()
    assert set(cfg["role_efforts"]) == set(cfg["role_models"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -q`
Expected: 3 failures (KeyError `autonomy`, old model IDs, KeyError `role_efforts`).

- [ ] **Step 3: Implement** — in `src/debussy/config.py`, replace the `role_models` value inside `DEFAULTS` and add two keys:

```python
    "role_models": {
        "conductor": "claude-fable-5",
        "developer": "claude-sonnet-5",
        "reviewer": "claude-opus-4-8",
        "security-reviewer": "claude-fable-5",
        "integrator": "claude-sonnet-5",
        "tester": "claude-sonnet-5",
    },
    "role_efforts": {
        "conductor": "high",
        "developer": "medium",
        "reviewer": "high",
        "security-reviewer": "high",
        "integrator": "low",
        "tester": "low",
    },
    "autonomy": "auto",
```

And extend `KNOWN_KEYS`:

```python
KNOWN_KEYS = {
    "max_total_agents", "use_tmux_windows", "base_branch",
    "paused", "agent_timeout", "agent_provider", "role_models",
    "docs_path", "notify_conductor", "max_role_agents", "monitor_interval",
    "project_type", "conductor_session_id", "test_command",
    "autonomy", "role_efforts",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -q`
Expected: all pass (the parametrized `test_known_keys_survive_clean_config` automatically covers the two new keys).

- [ ] **Step 5: Commit**

```bash
git add src/debussy/config.py tests/test_config.py
git commit -m "Add autonomy and role_efforts config, refresh role model defaults"
```

---

### Task 2: `role_cli_args()` helper in config.py

**Files:**
- Modify: `src/debussy/config.py` (append function after `parse_value`)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Task 1 defaults.
- Produces: `role_cli_args(role: str) -> list[str]` — e.g. `["--model", "claude-sonnet-5", "--effort", "medium"]`; empty list for unknown role; omits either flag when unset/empty. Consumed by Tasks 3 and 4.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_config.py` and extend the import line to `from debussy.config import KNOWN_KEYS, clean_config, get_config, role_cli_args, set_config`:

```python
def test_role_cli_args_returns_model_and_effort(project_dir):
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5", "--effort", "medium"]


def test_role_cli_args_empty_for_unknown_role(project_dir):
    assert role_cli_args("no-such-role") == []


def test_role_cli_args_omits_unset_effort(project_dir):
    set_config("role_efforts", {})
    assert role_cli_args("developer") == ["--model", "claude-sonnet-5"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -q`
Expected: ImportError (`role_cli_args` not defined).

- [ ] **Step 3: Implement** — append to `src/debussy/config.py`:

```python
def role_cli_args(role: str) -> list[str]:
    cfg = get_config()
    args = []
    model = cfg.get("role_models", {}).get(role)
    if model:
        args.extend(["--model", model])
    effort = cfg.get("role_efforts", {}).get(role)
    if effort:
        args.extend(["--effort", effort])
    return args
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/config.py tests/test_config.py
git commit -m "Add role_cli_args helper for per-role model and effort flags"
```

---

### Task 3: Wire `--effort` into spawner (both spawn paths)

**Files:**
- Modify: `src/debussy/spawner.py:10` (import), `src/debussy/spawner.py:78-89` (`_spawn_tmux`), `src/debussy/spawner.py:130-141` (`_spawn_background`)
- Test: `tests/test_spawner.py`

**Interfaces:**
- Consumes: `role_cli_args(role)` from Task 2.
- Produces: spawn commands containing `--model <m> --effort <e>` per role.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_spawner.py` (unittest style, matching the file). Add `import os`, `import shutil`, `import tempfile` to the file's imports:

```python
class TestSpawnCommandFlags(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    @patch("debussy.spawner.subprocess.run")
    @patch("debussy.spawner.role_cli_args", return_value=["--model", "claude-sonnet-5", "--effort", "medium"])
    @patch("debussy.spawner.get_config", return_value={"agent_provider": "claude"})
    def test_tmux_command_includes_model_and_effort(self, _cfg, _args, mock_run):
        from debussy.spawner import _spawn_tmux

        mock_run.return_value = MagicMock(stdout="@42\n", returncode=0)
        _spawn_tmux("developer-bach", "bd-1", "developer", Path("/tmp/p.md"), "msg", "stage:development")

        shell_cmd = mock_run.call_args_list[0][0][0][-1]
        self.assertIn("--model claude-sonnet-5", shell_cmd)
        self.assertIn("--effort medium", shell_cmd)

    @patch("debussy.spawner.subprocess.Popen")
    @patch("debussy.spawner.role_cli_args", return_value=["--model", "claude-sonnet-5", "--effort", "medium"])
    @patch("debussy.spawner.get_config", return_value={"agent_provider": "claude"})
    def test_background_command_includes_model_and_effort(self, _cfg, _args, mock_popen):
        from debussy.spawner import _spawn_background

        _spawn_background("developer-bach", "bd-1", "developer", "sys", "msg", "stage:development")

        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-sonnet-5")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_spawner.py -q`
Expected: 2 failures (AttributeError: `debussy.spawner` has no attribute `role_cli_args`).

- [ ] **Step 3: Implement** — in `src/debussy/spawner.py`, change the config import to:

```python
from .config import SESSION_NAME, YOLO_MODE, get_base_branch, get_config, log, role_cli_args
```

In `_spawn_tmux`, replace the model lookup and cli_cmd construction (currently reads `role_models`/`model` from cfg and appends `--model`):

```python
def _spawn_tmux(agent_name, task_id, role, prompt_path, user_message, stage, worktree_path=""):
    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")

    cli_cmd = agent_provider
    if agent_provider == "claude" and YOLO_MODE:
        cli_cmd += " --dangerously-skip-permissions"
    for arg in role_cli_args(role):
        cli_cmd += f" {shlex.quote(arg)}"
    cli_cmd += f" --system-prompt \"$(cat {shlex.quote(str(prompt_path))})\" {shlex.quote(user_message)}"
```

In `_spawn_background`, same replacement:

```python
def _spawn_background(agent_name, task_id, role, system_prompt, user_message, stage, worktree_path=""):
    cfg = get_config()
    agent_provider = cfg.get("agent_provider", "claude")

    cmd = [agent_provider]
    if agent_provider == "claude" and YOLO_MODE:
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(role_cli_args(role))
    cmd.extend(["--system-prompt", system_prompt, "--print", user_message])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_spawner.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/spawner.py tests/test_spawner.py
git commit -m "Pass per-role model and effort flags in agent spawn commands"
```

---

### Task 4: Wire `--effort` into the conductor command

**Files:**
- Modify: `src/debussy/tmux.py:11` (import), `src/debussy/tmux.py:76-81` (`_build_conductor_cmd`)
- Test: `tests/test_tmux.py`

**Interfaces:**
- Consumes: `role_cli_args("conductor")` from Task 2.
- Produces: conductor launch command containing `--model claude-fable-5 --effort high`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_tmux.py`:

```python
class TestBuildConductorCmd:
    def test_includes_model_and_effort_from_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from debussy.tmux import _build_conductor_cmd

        cmd = _build_conductor_cmd()

        assert "--model claude-fable-5" in cmd
        assert "--effort high" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tmux.py -q`
Expected: FAIL — `--effort high` not in cmd.

- [ ] **Step 3: Implement** — in `src/debussy/tmux.py`, change the config import to:

```python
from .config import SESSION_NAME, YOLO_MODE, get_config, role_cli_args, set_config
```

Replace the head of `_build_conductor_cmd` (drop the `cfg`/`conductor_model` lookup):

```python
def _build_conductor_cmd(requirement: str | None = None, resume: bool = False) -> str:
    claude_cmd = "claude --dangerously-skip-permissions" if YOLO_MODE else "claude"
    for arg in role_cli_args("conductor"):
        claude_cmd += f" {shlex.quote(arg)}"
```

The rest of the function (resume/session-id/prompt handling) is unchanged. If `get_config` is no longer referenced anywhere in `tmux.py` after this edit, remove it from the import; otherwise keep it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tmux.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/debussy/tmux.py tests/test_tmux.py
git commit -m "Pass conductor model and effort flags when building conductor command"
```

---

### Task 5: Supervision loop in conductor.md + autonomy injection

**Files:**
- Modify: `src/debussy/prompts/conductor.md:57-67`
- Modify: `src/debussy/prompts/__init__.py:108-111` (`get_conductor_system_prompt`)
- Test: `tests/test_prompts.py` (create)

**Interfaces:**
- Consumes: `get_config()["autonomy"]` from Task 1.
- Produces: `get_conductor_system_prompt()` returns prompt with `AUTONOMY_INSTRUCTIONS` and `MONITOR_INTERVAL` substituted.

- [ ] **Step 1: Write the failing tests** — create `tests/test_prompts.py`:

```python
"""Tests for conductor prompt assembly."""

import pytest

from debussy.config import set_config
from debussy.prompts import get_conductor_system_prompt


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_auto_mode_is_default(project_dir):
    text = get_conductor_system_prompt()
    assert "never ask the user mid-run" in text
    assert "AUTONOMY_INSTRUCTIONS" not in text


def test_manual_mode_injects_manual_instructions(project_dir):
    set_config("autonomy", "manual")
    text = get_conductor_system_prompt()
    assert "wait for the user's choice" in text
    assert "never ask the user mid-run" not in text


def test_unknown_autonomy_value_falls_back_to_auto(project_dir):
    set_config("autonomy", "bogus")
    text = get_conductor_system_prompt()
    assert "never ask the user mid-run" in text


def test_no_unsubstituted_placeholders(project_dir):
    text = get_conductor_system_prompt()
    assert "MONITOR_INTERVAL" not in text
    assert "AUTONOMY_INSTRUCTIONS" not in text


def test_supervision_sections_present(project_dir):
    text = get_conductor_system_prompt()
    assert "PIPELINE SUPERVISION" in text
    assert "DECISION PROTOCOL" in text
    assert "ESCALATION LADDER" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompts.py -q`
Expected: failures — supervision sections missing, `AUTONOMY_INSTRUCTIONS` not substituted.

- [ ] **Step 3: Rewrite conductor.md sections** — in `src/debussy/prompts/conductor.md`, replace lines 57-67 (the `MONITORING REJECTION LOOPS`, `RECOVERY`, `AGENT LOGS`, and `PIPELINE MONITORING` blocks) with:

```markdown
RECOVERY (stuck tasks):
takt advance <id> --to done               # skip permanently (only when the user asks)
takt advance <id> --to development         # retry

AGENT LOGS — .debussy/logs/<agent-name>.log and .debussy/logs/watcher.log. Read these to diagnose failures, rejections, or stuck tasks.

PIPELINE SUPERVISION:
After releasing tasks, run `sleep MONITOR_INTERVAL && debussy board` (use Bash tool with run_in_background parameter) to schedule checks. On each check: if nothing changed, schedule the next check silently; if something changed, diagnose (agent logs, takt show <id>, takt log <id>), act per the decision protocol, then schedule the next check. Supervise until every task is done or parked.

DECISION PROTOCOL:
- Decide yourself — never defer a decision you can make from the evidence at hand.
- If information is missing, spawn investigation subagents (Task tool), each with ONE specific question (e.g. "Why does test X fail on branch feature/PRJ-3? Root cause only, no fixes."). Evaluate the findings, pick the recommended solution, act on it.
- AUTONOMY_INSTRUCTIONS

ESCALATION LADDER — apply per failing task, in order:
1. Rejected 2+ times → read reviewer comments (takt show <id>), then rewrite the description, split the task, or add implementation hints. Don't re-release the same vague task.
2. Still failing → spawn an investigation subagent for the root cause (bad spec, missing dependency, environment issue). Re-plan: new task breakdown, different approach, or restructured deps.
3. After 2 failed re-plans → the task is not deliverable as specified. Park it: `takt block <id>` and do NOT advance it to done. Dependents stay parked automatically. Keep driving all independent tasks to done.
4. End of run → final report: what shipped, what was parked and why, what the parked tasks blocked.
```

- [ ] **Step 4: Implement autonomy injection** — in `src/debussy/prompts/__init__.py`, add after `_NO_BRANCH_ERROR`:

```python
_AUTONOMY_MODES = {
    "auto": (
        "AUTONOMY: full — never ask the user mid-run. Make every recovery and "
        "re-planning decision yourself. Log each decision to .debussy/conductor-context.md "
        "(what, why, alternatives considered). When every task is done or parked, "
        "produce the final report."
    ),
    "manual": (
        "AUTONOMY: manual — at each decision point (rejection loop, stuck agent, "
        "re-plan, parking), present the options with your recommendation and wait "
        "for the user's choice."
    ),
}
```

And replace `get_conductor_system_prompt`:

```python
def get_conductor_system_prompt() -> str:
    text = get_conductor_prompt_path().read_text()
    cfg = get_config()
    text = text.replace("MONITOR_INTERVAL", str(cfg.get("monitor_interval", 300)))
    mode = "manual" if cfg.get("autonomy") == "manual" else "auto"
    return text.replace("AUTONOMY_INSTRUCTIONS", _AUTONOMY_MODES[mode])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompts.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/debussy/prompts/conductor.md src/debussy/prompts/__init__.py tests/test_prompts.py
git commit -m "Add pipeline supervision loop and autonomy modes to conductor prompt"
```

---

### Task 6: Documentation

**Files:**
- Modify: `CLAUDE.md` (Commands section; @conductor section)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update CLAUDE.md** — in the Commands section, after the `debussy config test_command` line, add:

```markdown
debussy config autonomy manual               # Conductor asks at decision points (default: auto — never asks mid-run)
```

In the `@conductor` agent section, add one bullet after "Monitors progress with `debussy board`":

```markdown
- Supervises the pipeline until every task is done or parked: diagnoses failures, spawns investigation subagents when information is missing, and escalates per the ladder (rewrite → re-plan → park + report)
```

- [ ] **Step 2: Check README** — run `grep -n "role_models\|opus-4-6\|sonnet-4-6\|monitoring" README.md`. If stale model IDs or monitoring descriptions appear, update them to match the new defaults; if nothing matches, skip.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Document autonomy config and supervision behavior"
```

(Include README.md in the `git add` only if Step 2 changed it.)

---

### Task 7: Full suite, push, PR

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: all pass, no regressions.

- [ ] **Step 2: Push and create PR**

```bash
git push -u origin feature/conductor-autonomy
gh pr create --title "Conductor autonomy: supervision loop, autonomy modes, per-role model/effort" --body "..."
```

PR body: summarize the three changes (supervision loop + escalation ladder in conductor prompt, autonomy auto/manual config, refreshed model defaults + per-role effort), link the spec file, note the config migration caveat (existing `role_models` in `.debussy/config.json` shadows new defaults wholesale).
