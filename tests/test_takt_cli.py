"""Tests for takt CLI."""

import json
import os

import pytest

from debussy.takt.cli import main
from debussy.takt.db import init_db


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Set up a project directory with .git marker and initialized takt db."""
    (tmp_path / ".git").mkdir()
    init_db(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestInit:
    def test_creates_db(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert main(["init"]) == 0
        assert (tmp_path / ".takt" / "takt.db").is_file()


class TestCreate:
    def test_basic(self, project_dir, capsys):
        assert main(["create", "My task"]) == 0
        out = capsys.readouterr().out.strip()
        assert "-" in out
        parts = out.split("-")
        assert parts[0].isalpha() and parts[0].isupper()
        assert parts[1].isdigit()

    def test_with_description(self, project_dir, capsys):
        main(["create", "Task", "-d", "Some desc"])
        task_id = capsys.readouterr().out.strip()
        main(["show", task_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["description"] == "Some desc"

    def test_with_tags(self, project_dir, capsys):
        main(["create", "Task", "--tags", "security,frontend"])
        task_id = capsys.readouterr().out.strip()
        main(["show", task_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["tags"] == ["security", "frontend"]

    def test_with_deps(self, project_dir, capsys):
        main(["create", "Dep task"])
        dep_id = capsys.readouterr().out.strip()
        main(["create", "Main task", "--deps", dep_id])
        main_id = capsys.readouterr().out.strip()
        main(["show", main_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert dep_id in data["dependencies"]

    def test_with_project(self, project_dir, capsys):
        main(["project", "add", "FIX", "Fixes"])
        capsys.readouterr()
        assert main(["create", "Fix bug", "-p", "FIX"]) == 0
        task_id = capsys.readouterr().out.strip()
        assert task_id.startswith("FIX-")

    def test_with_unknown_project(self, project_dir):
        assert main(["create", "Fix bug", "-p", "ZZZ"]) == 1

    def test_cross_project_deps(self, project_dir, capsys):
        main(["create", "Default task"])
        default_id = capsys.readouterr().out.strip()
        main(["project", "add", "FIX", "Fixes"])
        capsys.readouterr()
        main(["create", "Fix task", "-p", "FIX", "--deps", default_id])
        fix_id = capsys.readouterr().out.strip()
        main(["show", fix_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert default_id in data["dependencies"]


class TestShow:
    def test_human_readable(self, project_dir, capsys):
        main(["create", "Test task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["show", task_id]) == 0
        out = capsys.readouterr().out
        assert "Test task" in out
        assert task_id in out

    def test_json_output(self, project_dir, capsys):
        main(["create", "Test task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["show", task_id, "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == task_id
        assert data["title"] == "Test task"

    def test_not_found(self, project_dir):
        assert main(["show", "XXX-999"]) == 1


class TestList:
    def test_empty(self, project_dir, capsys):
        assert main(["list"]) == 0
        assert "No tasks" in capsys.readouterr().out

    def test_with_tasks(self, project_dir, capsys):
        main(["create", "Task A"])
        capsys.readouterr()
        main(["create", "Task B"])
        capsys.readouterr()
        assert main(["list"]) == 0
        out = capsys.readouterr().out
        assert "Task A" in out
        assert "Task B" in out

    def test_json_output(self, project_dir, capsys):
        main(["create", "Task A"])
        capsys.readouterr()
        assert main(["list", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["title"] == "Task A"

    def test_filter_stage(self, project_dir, capsys):
        main(["create", "Task A"])
        task_id = capsys.readouterr().out.strip()
        main(["advance", task_id])
        capsys.readouterr()
        assert main(["list", "--stage", "development", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1

    def test_filter_project(self, project_dir, capsys):
        main(["create", "Default task"])
        capsys.readouterr()
        main(["project", "add", "FIX", "Fixes"])
        capsys.readouterr()
        main(["create", "Fix task", "-p", "FIX"])
        capsys.readouterr()
        assert main(["list", "-p", "FIX", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["title"] == "Fix task"


class TestWorkflow:
    def test_advance(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["advance", task_id]) == 0
        out = capsys.readouterr().out
        assert "development" in out

    def test_claim(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["claim", task_id, "--agent", "dev-1"]) == 0
        out = capsys.readouterr().out
        assert "claimed" in out

    def test_release(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        main(["claim", task_id, "--agent", "dev-1"])
        capsys.readouterr()
        assert main(["release", task_id]) == 0
        assert "released" in capsys.readouterr().out

    def test_reject(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["reject", task_id]) == 0
        assert "rejected" in capsys.readouterr().out

    def test_block(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["block", task_id]) == 0
        assert "blocked" in capsys.readouterr().out


class TestUpdate:
    def test_update_description(self, project_dir, capsys):
        main(["create", "Task", "-d", "Old desc"])
        task_id = capsys.readouterr().out.strip()
        assert main(["update", task_id, "-d", "New desc"]) == 0
        capsys.readouterr()
        main(["show", task_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["description"] == "New desc"

    def test_update_title(self, project_dir, capsys):
        main(["create", "Old title"])
        task_id = capsys.readouterr().out.strip()
        assert main(["update", task_id, "-t", "New title"]) == 0
        capsys.readouterr()
        main(["show", task_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["title"] == "New title"

    def test_update_tags(self, project_dir, capsys):
        main(["create", "Task", "--tags", "old"])
        task_id = capsys.readouterr().out.strip()
        assert main(["update", task_id, "--tags", "new,frontend"]) == 0
        capsys.readouterr()
        main(["show", task_id, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["tags"] == ["new", "frontend"]

    def test_update_nothing(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["update", task_id]) == 1

    def test_update_not_found(self, project_dir):
        assert main(["update", "XXX-999", "-d", "nope"]) == 1


class TestComment:
    def test_add_comment(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["comment", task_id, "Nice work"]) == 0
        assert "Comment added" in capsys.readouterr().out


class TestLog:
    def test_show_log(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        main(["advance", task_id])
        capsys.readouterr()
        assert main(["log", task_id]) == 0
        out = capsys.readouterr().out
        assert "transition" in out

    def test_filter_type(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        main(["advance", task_id])
        capsys.readouterr()
        main(["comment", task_id, "note"])
        capsys.readouterr()
        assert main(["log", task_id, "--type", "comment"]) == 0
        out = capsys.readouterr().out
        assert "note" in out
        assert "transition" not in out.split("comment")[0] if "comment" in out else True

    def test_empty_log(self, project_dir, capsys):
        main(["create", "Task"])
        task_id = capsys.readouterr().out.strip()
        assert main(["log", task_id]) == 0
        assert "No log" in capsys.readouterr().out


class TestProject:
    def test_add(self, project_dir, capsys):
        assert main(["project", "add", "FIX", "Hotfixes"]) == 0
        assert "FIX" in capsys.readouterr().out

    def test_add_default(self, project_dir, capsys):
        assert main(["project", "add", "FIX", "Hotfixes", "--default"]) == 0
        assert main(["project", "list"]) == 0
        out = capsys.readouterr().out
        assert "FIX" in out

    def test_add_invalid_prefix(self, project_dir):
        assert main(["project", "add", "X", "Too short"]) == 1

    def test_add_duplicate(self, project_dir):
        main(["project", "add", "FIX", "Hotfixes"])
        assert main(["project", "add", "FIX", "Again"]) == 1

    def test_list(self, project_dir, capsys):
        main(["project", "add", "FIX", "Hotfixes"])
        capsys.readouterr()
        assert main(["project", "list"]) == 0
        out = capsys.readouterr().out
        assert "FIX" in out

    def test_default_switch(self, project_dir, capsys):
        main(["project", "add", "FIX", "Hotfixes"])
        capsys.readouterr()
        assert main(["project", "default", "FIX"]) == 0
        assert main(["project", "list"]) == 0
        out = capsys.readouterr().out
        assert "FIX" in out

    def test_default_show(self, project_dir, capsys):
        assert main(["project", "default"]) == 0
        out = capsys.readouterr().out.strip()
        assert out.isalpha() and out.isupper()

    def test_rm(self, project_dir, capsys):
        main(["project", "add", "FIX", "Hotfixes"])
        capsys.readouterr()
        assert main(["project", "rm", "FIX"]) == 0

    def test_rm_with_tasks_fails(self, project_dir, capsys):
        main(["project", "default"])
        orig = capsys.readouterr().out.strip()
        main(["project", "add", "FIX", "Hotfixes", "--default"])
        capsys.readouterr()
        main(["create", "A task"])
        capsys.readouterr()
        main(["project", "default", orig])
        capsys.readouterr()
        assert main(["project", "rm", "FIX"]) == 1

    def test_rm_default_fails(self, project_dir, capsys):
        main(["project", "default"])
        prefix = capsys.readouterr().out.strip()
        assert main(["project", "rm", prefix]) == 1


class TestPrefixDeprecated:
    def test_prefix_show_still_works(self, project_dir, capsys):
        assert main(["prefix"]) == 0
        out = capsys.readouterr()
        assert out.out.strip().isalpha()
        assert "deprecated" in out.err.lower()

    def test_prefix_set_still_works(self, project_dir, capsys):
        main(["project", "add", "NEW", "New project"])
        capsys.readouterr()
        assert main(["prefix", "NEW"]) == 0
        err = capsys.readouterr().err
        assert "deprecated" in err.lower()

    def test_prefix_set_nonexistent_fails(self, project_dir):
        assert main(["prefix", "ZZZ"]) == 1


class TestNoCommand:
    def test_no_args(self, project_dir):
        assert main([]) == 1
