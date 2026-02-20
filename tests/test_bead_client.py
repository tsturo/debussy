import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from debussy.bead_client import (
    get_bead_json,
    get_bead_status,
    get_all_beads,
    update_bead,
    comment_bead,
    get_unresolved_deps,
)


def _make_result(stdout="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.returncode = returncode
    return r


class TestGetBeadJson:
    @patch("debussy.bead_client.subprocess.run")
    def test_valid_response(self, mock_run):
        bead = {"id": "bd-001", "status": "open"}
        mock_run.return_value = _make_result(json.dumps([bead]))
        assert get_bead_json("bd-001") == bead
        mock_run.assert_called_once_with(
            ["bd", "show", "bd-001", "--json"],
            capture_output=True, text=True, timeout=5,
        )

    @patch("debussy.bead_client.subprocess.run")
    def test_empty_list(self, mock_run):
        mock_run.return_value = _make_result(json.dumps([]))
        assert get_bead_json("bd-001") is None

    @patch("debussy.bead_client.subprocess.run")
    def test_invalid_json(self, mock_run):
        mock_run.return_value = _make_result("not json")
        assert get_bead_json("bd-001") is None

    @patch("debussy.bead_client.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bd", timeout=5)
        assert get_bead_json("bd-001") is None

    @patch("debussy.bead_client.subprocess.run")
    def test_non_list_response(self, mock_run):
        mock_run.return_value = _make_result(json.dumps({"id": "bd-001"}))
        assert get_bead_json("bd-001") is None


class TestGetBeadStatus:
    @patch("debussy.bead_client.get_bead_json")
    def test_returns_status(self, mock_get):
        mock_get.return_value = {"id": "bd-001", "status": "open"}
        assert get_bead_status("bd-001") == "open"

    @patch("debussy.bead_client.get_bead_json")
    def test_returns_none_when_bead_missing(self, mock_get):
        mock_get.return_value = None
        assert get_bead_status("bd-999") is None


class TestGetAllBeads:
    @patch("debussy.bead_client.subprocess.run")
    def test_collects_from_all_statuses(self, mock_run):
        open_beads = [{"id": "bd-001", "status": "open"}]
        closed_beads = [{"id": "bd-002", "status": "closed"}]

        def side_effect(cmd, **kwargs):
            status = cmd[cmd.index("--status") + 1]
            if status == "open":
                return _make_result(json.dumps(open_beads))
            if status == "closed":
                return _make_result(json.dumps(closed_beads))
            return _make_result("", returncode=1)

        mock_run.side_effect = side_effect
        result = get_all_beads()
        ids = {b["id"] for b in result}
        assert ids == {"bd-001", "bd-002"}

    @patch("debussy.bead_client.subprocess.run")
    def test_deduplicates_by_id(self, mock_run):
        bead = {"id": "bd-001", "status": "open"}
        mock_run.return_value = _make_result(json.dumps([bead]))
        result = get_all_beads()
        assert sum(1 for b in result if b["id"] == "bd-001") == 1

    @patch("debussy.bead_client.subprocess.run")
    def test_handles_all_failures(self, mock_run):
        mock_run.return_value = _make_result("", returncode=1)
        assert get_all_beads() == []

    @patch("debussy.bead_client.subprocess.run")
    def test_skips_beads_without_id(self, mock_run):
        beads = [{"status": "open"}, {"id": "bd-001", "status": "open"}]
        mock_run.return_value = _make_result(json.dumps(beads))
        result = get_all_beads()
        assert len(result) == 1
        assert result[0]["id"] == "bd-001"


class TestUpdateBead:
    @patch("debussy.bead_client.subprocess.run")
    def test_status_only(self, mock_run):
        mock_run.return_value = _make_result()
        update_bead("bd-001", status="closed")
        mock_run.assert_called_once_with(
            ["bd", "update", "bd-001", "--status", "closed"],
            capture_output=True, text=True, timeout=5,
        )

    @patch("debussy.bead_client.subprocess.run")
    def test_add_and_remove_labels(self, mock_run):
        mock_run.return_value = _make_result()
        update_bead("bd-001", add_labels=["stage:reviewing"], remove_labels=["stage:development"])
        mock_run.assert_called_once_with(
            ["bd", "update", "bd-001",
             "--add-label", "stage:reviewing",
             "--remove-label", "stage:development"],
            capture_output=True, text=True, timeout=5,
        )

    @patch("debussy.bead_client.subprocess.run")
    def test_noop_when_nothing_to_update(self, mock_run):
        result = update_bead("bd-001")
        mock_run.assert_not_called()
        assert result is None

    @patch("debussy.bead_client.subprocess.run")
    def test_all_params(self, mock_run):
        mock_run.return_value = _make_result()
        update_bead("bd-001", status="open", add_labels=["a"], remove_labels=["b"])
        cmd = mock_run.call_args[0][0]
        assert cmd == ["bd", "update", "bd-001", "--status", "open", "--add-label", "a", "--remove-label", "b"]


class TestCommentBead:
    @patch("debussy.bead_client.subprocess.run")
    def test_sends_comment(self, mock_run):
        comment_bead("bd-001", "test comment")
        mock_run.assert_called_once_with(
            ["bd", "comment", "bd-001", "test comment"],
            capture_output=True, timeout=5,
        )


class TestGetUnresolvedDeps:
    def test_no_dependencies(self):
        assert get_unresolved_deps({"id": "bd-001"}) == []

    def test_all_closed(self):
        bead = {"dependencies": [
            {"depends_on_id": "bd-002", "status": "closed"},
            {"depends_on_id": "bd-003", "status": "closed"},
        ]}
        assert get_unresolved_deps(bead) == []

    def test_some_unresolved(self):
        bead = {"dependencies": [
            {"depends_on_id": "bd-002", "status": "closed"},
            {"depends_on_id": "bd-003", "status": "open"},
        ]}
        assert get_unresolved_deps(bead) == ["bd-003"]

    def test_uses_id_fallback(self):
        bead = {"dependencies": [
            {"id": "bd-002", "status": "open"},
        ]}
        assert get_unresolved_deps(bead) == ["bd-002"]

    def test_skips_deps_without_id(self):
        bead = {"dependencies": [{"status": "open"}]}
        assert get_unresolved_deps(bead) == []

    @patch("debussy.bead_client.get_bead_status")
    def test_falls_back_to_get_bead_status(self, mock_status):
        mock_status.return_value = "open"
        bead = {"dependencies": [{"depends_on_id": "bd-002"}]}
        assert get_unresolved_deps(bead) == ["bd-002"]
        mock_status.assert_called_once_with("bd-002")

    @patch("debussy.bead_client.get_bead_status")
    def test_fallback_closed_resolves(self, mock_status):
        mock_status.return_value = "closed"
        bead = {"dependencies": [{"depends_on_id": "bd-002"}]}
        assert get_unresolved_deps(bead) == []
