# Session CLI Commands Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `debussy sessions` and `debussy connect` commands to list and attach to running debussy tmux sessions.

**Architecture:** Query tmux directly for `debussy-*` sessions and extract project paths from pane working directories. No registry files or extra state.

**Tech Stack:** Python subprocess calls to tmux CLI.

---

### Task 1: Add `list_debussy_sessions()` to tmux.py

**Files:**
- Modify: `src/debussy/tmux.py`
- Test: `tests/test_tmux.py`

**Step 1: Write the failing test**

Create `tests/test_tmux.py`:

```python
from unittest.mock import patch, MagicMock

from debussy.tmux import list_debussy_sessions


class TestListDebussySessions:
    @patch("debussy.tmux.subprocess.run")
    def test_returns_sessions_with_paths(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="debussy-piklr\ndebussy-myapp\nother-session\n"),
            MagicMock(returncode=0, stdout="/root/projects/piklr\n"),
            MagicMock(returncode=0, stdout="/root/projects/myapp\n"),
        ]

        result = list_debussy_sessions()

        assert result == [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]

    @patch("debussy.tmux.subprocess.run")
    def test_returns_empty_when_no_tmux(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = list_debussy_sessions()

        assert result == []

    @patch("debussy.tmux.subprocess.run")
    def test_returns_empty_when_no_debussy_sessions(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="other-session\n")

        result = list_debussy_sessions()

        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_tmux.py -v`
Expected: FAIL with ImportError (list_debussy_sessions not defined)

**Step 3: Write minimal implementation**

Add to `src/debussy/tmux.py`:

```python
def list_debussy_sessions() -> list[dict]:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    sessions = []
    for name in result.stdout.strip().split('\n'):
        if not name.startswith("debussy-"):
            continue
        path_result = subprocess.run(
            ["tmux", "display-message", "-t", f"{name}:main.0", "-p", "#{pane_current_path}"],
            capture_output=True, text=True,
        )
        path = path_result.stdout.strip() if path_result.returncode == 0 else "unknown"
        sessions.append({"session": name, "path": path})
    return sessions
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_tmux.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_tmux.py src/debussy/tmux.py
git commit -m "[debussy] add list_debussy_sessions to tmux module"
```

---

### Task 2: Add `cmd_sessions()` to cli.py

**Files:**
- Modify: `src/debussy/cli.py`
- Test: `tests/test_cli_sessions.py`

**Step 1: Write the failing test**

Create `tests/test_cli_sessions.py`:

```python
from unittest.mock import patch, MagicMock

from debussy.cli import cmd_sessions


class TestCmdSessions:
    @patch("debussy.cli.list_debussy_sessions")
    def test_prints_sessions(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]

        cmd_sessions(MagicMock())

        output = capsys.readouterr().out
        assert "debussy-piklr" in output
        assert "/root/projects/piklr" in output
        assert "debussy-myapp" in output

    @patch("debussy.cli.list_debussy_sessions")
    def test_prints_no_sessions(self, mock_list, capsys):
        mock_list.return_value = []

        cmd_sessions(MagicMock())

        output = capsys.readouterr().out
        assert "No active sessions" in output
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_cli_sessions.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add import to `src/debussy/cli.py` (in the existing tmux import):

```python
from .tmux import (
    create_tmux_layout, kill_agent, label_panes, list_debussy_sessions,
    send_conductor_prompt,
)
```

Add function to `src/debussy/cli.py`:

```python
def cmd_sessions(args):
    sessions = list_debussy_sessions()
    if not sessions:
        print("No active sessions")
        return 0
    for s in sessions:
        print(f"  {s['session']}    {s['path']}")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_cli_sessions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_cli_sessions.py src/debussy/cli.py
git commit -m "[debussy] add sessions command to list running sessions"
```

---

### Task 3: Add `cmd_connect()` to cli.py

**Files:**
- Modify: `src/debussy/cli.py`
- Modify: `tests/test_cli_sessions.py`

**Step 1: Write the failing test**

Add to `tests/test_cli_sessions.py`:

```python
from debussy.cli import cmd_connect


class TestCmdConnect:
    @patch("debussy.cli.os.execvp")
    @patch("debussy.cli.os.chdir")
    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_by_name(self, mock_list, mock_chdir, mock_exec):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = "piklr"

        cmd_connect(args)

        mock_chdir.assert_called_once_with("/root/projects/piklr")
        mock_exec.assert_called_once_with(
            "tmux", ["tmux", "attach-session", "-t", "debussy-piklr"]
        )

    @patch("debussy.cli.os.execvp")
    @patch("debussy.cli.os.chdir")
    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_auto_single_session(self, mock_list, mock_chdir, mock_exec):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = None

        cmd_connect(args)

        mock_chdir.assert_called_once_with("/root/projects/piklr")
        mock_exec.assert_called_once()

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_no_sessions(self, mock_list, capsys):
        mock_list.return_value = []
        args = MagicMock()
        args.name = "piklr"

        result = cmd_connect(args)

        assert result == 1
        assert "No active sessions" in capsys.readouterr().out

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_multiple_no_name(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
            {"session": "debussy-myapp", "path": "/root/projects/myapp"},
        ]
        args = MagicMock()
        args.name = None

        result = cmd_connect(args)

        assert result == 1
        output = capsys.readouterr().out
        assert "debussy-piklr" in output

    @patch("debussy.cli.list_debussy_sessions")
    def test_connect_name_not_found(self, mock_list, capsys):
        mock_list.return_value = [
            {"session": "debussy-piklr", "path": "/root/projects/piklr"},
        ]
        args = MagicMock()
        args.name = "notfound"

        result = cmd_connect(args)

        assert result == 1
        assert "not found" in capsys.readouterr().out
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_cli_sessions.py::TestCmdConnect -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

Add to `src/debussy/cli.py`:

```python
def _find_session(sessions: list[dict], name: str) -> dict | None:
    target = f"debussy-{name}" if not name.startswith("debussy-") else name
    for s in sessions:
        if s["session"] == target:
            return s
    return None


def cmd_connect(args):
    sessions = list_debussy_sessions()
    if not sessions:
        print("No active sessions")
        return 1

    name = getattr(args, "name", None)

    if not name:
        if len(sessions) == 1:
            session = sessions[0]
        else:
            print("Multiple sessions running. Specify a name:")
            for s in sessions:
                print(f"  {s['session']}    {s['path']}")
            return 1
    else:
        session = _find_session(sessions, name)
        if not session:
            print(f"Session '{name}' not found. Active sessions:")
            for s in sessions:
                print(f"  {s['session']}    {s['path']}")
            return 1

    os.chdir(session["path"])
    os.execvp("tmux", ["tmux", "attach-session", "-t", session["session"]])
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/test_cli_sessions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_cli_sessions.py src/debussy/cli.py
git commit -m "[debussy] add connect command to attach to running session"
```

---

### Task 4: Register subcommands in __main__.py

**Files:**
- Modify: `src/debussy/__main__.py`

**Step 1: Add subparsers**

After the `metrics` subparser block in `__main__.py`, add:

```python
p = subparsers.add_parser("sessions", help="List running debussy sessions")
p.set_defaults(func=cli.cmd_sessions)

p = subparsers.add_parser("connect", help="Attach to a running session")
p.add_argument("name", nargs="?", help="Session name (e.g. piklr)")
p.set_defaults(func=cli.cmd_connect)
```

**Step 2: Run all tests**

Run: `cd /Users/tomek/dev/ai/debussy && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Manual smoke test**

Run: `cd /Users/tomek/dev/ai/debussy && debussy sessions`
Expected: "No active sessions" (or lists any running sessions)

**Step 4: Commit**

```bash
git add src/debussy/__main__.py
git commit -m "[debussy] register sessions and connect subcommands"
```
