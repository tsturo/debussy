"""Tests for the quota detection layer (ccusage + limit-signal parsing)."""

import json
import subprocess
from datetime import datetime, timezone

import pytest

from debussy import quota
from debussy.quota import QuotaStatus, check_quota

ACTIVE_BLOCK = {
    "blocks": [
        {
            "id": "2026-07-07T06:00:00.000Z",
            "isActive": True,
            "endTime": "2026-07-07T11:00:00.000Z",
            "totalTokens": 100,
            "tokenLimitStatus": {"limit": 1000},
        }
    ]
}


def _fake_run(stdout="", returncode=0, raises=None):
    def runner(*args, **kwargs):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return runner


def test_check_quota_below_margin_not_exhausted(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    status = check_quota("ccusage blocks --active --json --token-limit max", 0.97)
    assert status is not None
    assert status.used == 100
    assert status.limit == 1000
    assert status.exhausted is False


def test_check_quota_at_or_above_margin_exhausted(monkeypatch):
    data = json.loads(json.dumps(ACTIVE_BLOCK))
    data["blocks"][0]["totalTokens"] = 970
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(data)))
    status = check_quota("cmd", 0.97)
    assert status.exhausted is True


def test_check_quota_reset_at_parsed_from_endtime(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    status = check_quota("cmd", 0.97)
    expected = datetime(2026, 7, 7, 11, 0, 0, tzinfo=timezone.utc).timestamp()
    assert status.reset_at == pytest.approx(expected)


@pytest.mark.parametrize("kwargs", [
    {"returncode": 1, "stdout": ""},
    {"stdout": "not json"},
    {"stdout": ""},
    {"stdout": json.dumps({"blocks": []})},
    {"stdout": json.dumps({"blocks": [{"isActive": True, "totalTokens": 5,
                                       "tokenLimitStatus": {"limit": 0}}]})},
])
def test_check_quota_fails_open_to_none(monkeypatch, kwargs):
    monkeypatch.setattr(subprocess, "run", _fake_run(**kwargs))
    assert check_quota("cmd", 0.97) is None


def test_check_quota_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        _fake_run(raises=subprocess.TimeoutExpired("cmd", 15)))
    assert check_quota("cmd", 0.97) is None


def test_check_quota_malformed_margin_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(ACTIVE_BLOCK)))
    assert check_quota("cmd", "not-a-number") is None
