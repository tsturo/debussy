from unittest.mock import MagicMock, patch

import pytest

from debussy.transitions import (
    MAX_REJECTIONS, MAX_RETRIES, TransitionResult,
    _compute_next_stage, _dispatch_transition, _handle_advance,
    _handle_empty_branch, _is_terminal_stage,
)


def _make_agent(bead="bd-001", spawned_stage="stage:development"):
    agent = MagicMock()
    agent.bead = bead
    agent.spawned_stage = spawned_stage
    return agent


def _make_watcher():
    watcher = MagicMock()
    watcher.rejections = {}
    watcher.cooldowns = {}
    watcher.empty_branch_retries = {}
    return watcher


class TestDispatchAdvance:
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_development_to_reviewing(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "open", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.remove_labels == ["stage:development"]
        assert result.add_labels == ["stage:reviewing"]
        assert result.status is None

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_reviewing_to_merging(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": ["stage:reviewing"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:merging"]
        assert "stage:reviewing" in result.remove_labels


class TestSecurityRouting:
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_reviewing_routes_to_security_review(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": ["stage:reviewing", "security"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:security-review"]

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_security_review_to_merging(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:security-review")
        bead = {"status": "open", "labels": ["stage:security-review", "security"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:merging"]


class TestRejection:
    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.record_event")
    def test_rejection_sends_to_development(self, mock_event, mock_run):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": ["stage:reviewing", "rejected"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:development"]
        assert "stage:reviewing" in result.remove_labels
        assert "rejected" in result.remove_labels
        assert watcher.rejections["bd-001"] == 1

    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.record_event")
    def test_max_rejections_blocks(self, mock_event, mock_run):
        watcher = _make_watcher()
        watcher.rejections["bd-001"] = MAX_REJECTIONS - 1
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": ["stage:reviewing", "rejected"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "blocked"
        assert result.add_labels == []


class TestAcceptanceRejection:
    @patch("debussy.transitions.record_event")
    def test_acceptance_rejection_blocks(self, mock_event):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:acceptance")
        bead = {"status": "open", "labels": ["stage:acceptance", "rejected"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "blocked"
        assert "rejected" in result.remove_labels


class TestInProgressReset:
    def test_resets_to_open(self):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "in_progress", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "open"


class TestClosed:
    @patch("debussy.transitions.validate_bead_pipeline", return_value=(True, "bd-001: ok"))
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions.record_event")
    def test_closed_removes_stage(self, mock_event, mock_delete, mock_verify, mock_audit):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status is None
        assert "stage:merging" in result.remove_labels
        mock_delete.assert_called_once_with("feature/bd-001")

    @patch("debussy.transitions.validate_bead_pipeline", return_value=(True, "bd-001: ok"))
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions.record_event")
    def test_closed_clears_rejections(self, mock_event, mock_delete, mock_verify, mock_audit):
        watcher = _make_watcher()
        watcher.rejections["bd-001"] = 3
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging"]}

        _dispatch_transition(watcher, agent, bead)

        assert "bd-001" not in watcher.rejections


class TestBlocked:
    @patch("debussy.transitions.record_event")
    def test_blocked_removes_stage(self, mock_event):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "blocked", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert "stage:development" in result.remove_labels
        assert result.status is None


class TestExternalRemoval:
    def test_stage_removed_externally(self):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": []}

        result = _dispatch_transition(watcher, agent, bead)

        assert not result.add_labels
        assert not result.remove_labels

    def test_stage_removed_with_rejected_cleans_up(self):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "open", "labels": ["rejected"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.remove_labels == ["rejected"]


class TestEmptyBranch:
    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.record_event")
    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_retries(self, mock_cfg, mock_commits, mock_event, mock_run):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "open", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:development"]
        assert "stage:development" in result.remove_labels
        assert watcher.empty_branch_retries["bd-001"] == 1

    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.record_event")
    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_empty_branch_max_retries_blocks(self, mock_cfg, mock_commits, mock_event, mock_run):
        watcher = _make_watcher()
        watcher.empty_branch_retries["bd-001"] = MAX_RETRIES - 1
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "open", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "blocked"


class TestComputeNextStage:
    def test_development_to_reviewing(self):
        agent = _make_agent(spawned_stage="stage:development")
        assert _compute_next_stage(agent, []) == "stage:reviewing"

    def test_reviewing_to_merging(self):
        agent = _make_agent(spawned_stage="stage:reviewing")
        assert _compute_next_stage(agent, []) == "stage:merging"

    def test_reviewing_security_to_security_review(self):
        agent = _make_agent(spawned_stage="stage:reviewing")
        assert _compute_next_stage(agent, ["security"]) == "stage:security-review"

    def test_security_review_to_merging(self):
        agent = _make_agent(spawned_stage="stage:security-review")
        assert _compute_next_stage(agent, []) == "stage:merging"

    def test_merging_is_terminal(self):
        agent = _make_agent(spawned_stage="stage:merging")
        assert _compute_next_stage(agent, []) is None

    def test_acceptance_is_terminal(self):
        agent = _make_agent(spawned_stage="stage:acceptance")
        assert _compute_next_stage(agent, []) is None


class TestPrematureClose:
    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_developer_close_reopens_and_advances(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "closed", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "open"
        assert result.add_labels == ["stage:reviewing"]
        assert "stage:development" in result.remove_labels

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_reviewer_close_reopens_and_advances(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:reviewing")
        bead = {"status": "closed", "labels": ["stage:reviewing"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "open"
        assert result.add_labels == ["stage:merging"]
        assert "stage:reviewing" in result.remove_labels

    @patch("debussy.transitions._branch_has_commits", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_security_reviewer_close_reopens_and_advances(self, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:security-review")
        bead = {"status": "closed", "labels": ["stage:security-review"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "open"
        assert result.add_labels == ["stage:merging"]
        assert "stage:security-review" in result.remove_labels

    @patch("debussy.transitions._branch_has_commits", return_value=False)
    @patch("debussy.transitions.record_event")
    @patch("debussy.transitions.get_config", return_value={"base_branch": "master"})
    def test_developer_close_with_empty_branch_retries(self, mock_cfg, mock_event, mock_commits):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:development")
        bead = {"status": "closed", "labels": ["stage:development"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.add_labels == ["stage:development"]
        assert result.status == "open"


class TestMergeVerification:
    @patch("debussy.transitions.validate_bead_pipeline", return_value=(True, "bd-001: ok"))
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.delete_branch")
    @patch("debussy.transitions.record_event")
    def test_verified_merge_closes(self, mock_event, mock_delete, mock_verify, mock_audit):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status is None
        assert "stage:merging" in result.remove_labels
        mock_delete.assert_called_once()

    @patch("debussy.transitions._verify_merge_landed", return_value=False)
    @patch("debussy.transitions.record_event")
    def test_unverified_merge_retries(self, mock_event, mock_verify):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "open"
        assert result.add_labels == ["stage:merging"]
        assert "stage:merging" in result.remove_labels

    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.validate_bead_pipeline", return_value=(False, "bd-001: missing stages: reviewing"))
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_incomplete_pipeline_blocks(self, mock_event, mock_verify, mock_audit, mock_run):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "blocked"
        assert "stage:merging" in result.remove_labels
        assert result.add_labels == []

    @patch("debussy.transitions.subprocess.run")
    @patch("debussy.transitions.validate_bead_pipeline", return_value=(False, "bd-001 (security): missing stages: security-review"))
    @patch("debussy.transitions._verify_merge_landed", return_value=True)
    @patch("debussy.transitions.record_event")
    def test_incomplete_security_pipeline_blocks(self, mock_event, mock_verify, mock_audit, mock_run):
        watcher = _make_watcher()
        agent = _make_agent(spawned_stage="stage:merging")
        bead = {"status": "closed", "labels": ["stage:merging", "security"]}

        result = _dispatch_transition(watcher, agent, bead)

        assert result.status == "blocked"


class TestTerminalStage:
    def test_development_is_not_terminal(self):
        assert not _is_terminal_stage("stage:development")

    def test_reviewing_is_not_terminal(self):
        assert not _is_terminal_stage("stage:reviewing")

    def test_security_review_is_not_terminal(self):
        assert not _is_terminal_stage("stage:security-review")

    def test_merging_is_terminal(self):
        assert _is_terminal_stage("stage:merging")

    def test_acceptance_is_terminal(self):
        assert _is_terminal_stage("stage:acceptance")

    def test_investigating_is_terminal(self):
        assert _is_terminal_stage("stage:investigating")


class TestTransitionResult:
    def test_no_changes(self):
        assert not TransitionResult().has_changes

    def test_status_is_change(self):
        assert TransitionResult(status="open").has_changes

    def test_add_labels_is_change(self):
        assert TransitionResult(add_labels=["stage:reviewing"]).has_changes

    def test_remove_labels_is_change(self):
        assert TransitionResult(remove_labels=["stage:development"]).has_changes
