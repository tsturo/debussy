from unittest.mock import patch

import pytest

from debussy.audit import (
    audit_acceptance, audit_dep_bead, expected_stages, get_completed_stages,
)
from debussy.config import (
    STAGE_DEVELOPMENT, STAGE_MERGING, STAGE_REVIEWING, STAGE_SECURITY_REVIEW,
)


def _advance(frm, to):
    return {"event": "advance", "from": frm, "to": to, "bead": "bd-001", "ts": 1.0}


def _close(stage):
    return {"event": "close", "stage": stage, "bead": "bd-001", "ts": 2.0}


def _reject(frm, to):
    return {"event": "reject", "from": frm, "to": to, "bead": "bd-001", "ts": 1.5}


class TestGetCompletedStages:
    def test_advance_collects_from_stages(self):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_MERGING),
        ]
        assert get_completed_stages(events) == {STAGE_DEVELOPMENT, STAGE_REVIEWING}

    def test_close_collects_terminal_stage(self):
        events = [_close(STAGE_MERGING)]
        assert get_completed_stages(events) == {STAGE_MERGING}

    def test_rejections_not_counted(self):
        events = [_reject(STAGE_REVIEWING, STAGE_DEVELOPMENT)]
        assert get_completed_stages(events) == set()

    def test_full_normal_trail(self):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        completed = get_completed_stages(events)
        assert completed == {STAGE_DEVELOPMENT, STAGE_REVIEWING, STAGE_MERGING}


class TestExpectedStages:
    def test_normal_bead(self):
        assert expected_stages(False) == {STAGE_DEVELOPMENT, STAGE_REVIEWING, STAGE_MERGING}

    def test_security_bead(self):
        assert expected_stages(True) == {
            STAGE_DEVELOPMENT, STAGE_REVIEWING, STAGE_SECURITY_REVIEW, STAGE_MERGING,
        }


class TestAuditDepBead:
    @patch("debussy.audit.get_bead_json", return_value={"labels": []})
    def test_normal_bead_complete_trail_passes(self, _):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        ok, detail = audit_dep_bead("bd-001", events)
        assert ok
        assert "ok" in detail

    @patch("debussy.audit.get_bead_json", return_value={"labels": ["security"]})
    def test_security_bead_complete_trail_passes(self, _):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_SECURITY_REVIEW),
            _advance(STAGE_SECURITY_REVIEW, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        ok, detail = audit_dep_bead("bd-001", events)
        assert ok

    @patch("debussy.audit.get_bead_json", return_value={"labels": ["security"]})
    def test_security_bead_missing_security_review_fails(self, _):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        ok, detail = audit_dep_bead("bd-001", events)
        assert not ok
        assert "security-review" in detail

    @patch("debussy.audit.get_bead_json", return_value={"labels": []})
    def test_missing_review_stage_fails(self, _):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        ok, detail = audit_dep_bead("bd-001", events)
        assert not ok
        assert "reviewing" in detail

    @patch("debussy.audit.get_bead_json", return_value={"labels": []})
    def test_rejection_then_full_completion_passes(self, _):
        events = [
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _reject(STAGE_REVIEWING, STAGE_DEVELOPMENT),
            _advance(STAGE_DEVELOPMENT, STAGE_REVIEWING),
            _advance(STAGE_REVIEWING, STAGE_MERGING),
            _close(STAGE_MERGING),
        ]
        ok, detail = audit_dep_bead("bd-001", events)
        assert ok

    @patch("debussy.audit.get_bead_json", return_value={"labels": []})
    def test_no_events_fails(self, _):
        ok, detail = audit_dep_bead("bd-001", [])
        assert not ok
        assert "no pipeline events" in detail


class TestAuditAcceptance:
    @patch("debussy.audit.get_bead_json")
    @patch("debussy.audit._load_all_events")
    def test_no_deps_passes(self, mock_events, mock_bead):
        mock_bead.return_value = {"dependencies": []}
        mock_events.return_value = []
        ok, report = audit_acceptance("bd-010")
        assert ok

    @patch("debussy.audit.get_bead_json")
    @patch("debussy.audit._load_all_events")
    def test_missing_bead_fails(self, mock_events, mock_bead):
        mock_bead.return_value = None
        ok, report = audit_acceptance("bd-010")
        assert not ok

    @patch("debussy.audit.get_bead_json")
    @patch("debussy.audit._load_all_events")
    def test_dep_with_no_events_fails(self, mock_events, mock_bead):
        def bead_lookup(bead_id):
            if bead_id == "bd-010":
                return {"dependencies": [{"depends_on_id": "bd-001"}]}
            return {"labels": []}
        mock_bead.side_effect = bead_lookup
        mock_events.return_value = []

        ok, report = audit_acceptance("bd-010")
        assert not ok
        assert "bd-001" in report

    @patch("debussy.audit.get_bead_json")
    @patch("debussy.audit._load_all_events")
    def test_all_deps_complete_passes(self, mock_events, mock_bead):
        def bead_lookup(bead_id):
            if bead_id == "bd-010":
                return {"dependencies": [
                    {"depends_on_id": "bd-001"},
                    {"depends_on_id": "bd-002"},
                ]}
            return {"labels": []}
        mock_bead.side_effect = bead_lookup
        mock_events.return_value = [
            {"event": "advance", "from": STAGE_DEVELOPMENT, "to": STAGE_REVIEWING, "bead": "bd-001", "ts": 1.0},
            {"event": "advance", "from": STAGE_REVIEWING, "to": STAGE_MERGING, "bead": "bd-001", "ts": 2.0},
            {"event": "close", "stage": STAGE_MERGING, "bead": "bd-001", "ts": 3.0},
            {"event": "advance", "from": STAGE_DEVELOPMENT, "to": STAGE_REVIEWING, "bead": "bd-002", "ts": 1.0},
            {"event": "advance", "from": STAGE_REVIEWING, "to": STAGE_MERGING, "bead": "bd-002", "ts": 2.0},
            {"event": "close", "stage": STAGE_MERGING, "bead": "bd-002", "ts": 3.0},
        ]

        ok, report = audit_acceptance("bd-010")
        assert ok
